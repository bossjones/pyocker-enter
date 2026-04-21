from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import docker.errors
import pytest

from pyocker_enter.docker_utils import (
    ContainerRecord,
    enter_container,
    list_running_containers,
    probe_available_shells,
)
from pyocker_enter.errors import CLIError, ExitCode


class _FakeImage:
    def __init__(self, tags: list[str]) -> None:
        self.tags = tags


class _FakeContainer:
    def __init__(
        self,
        *,
        container_id: str,
        name: str,
        image_tags: list[str],
        status: str = "running",
        started_at: str = "2026-04-21T00:00:00.000000",
    ) -> None:
        self.id = container_id
        self.name = name
        self.image = _FakeImage(image_tags)
        self.status = status
        self.attrs = {"State": {"StartedAt": started_at}}


def test_list_running_containers_returns_dataclass_records(monkeypatch: pytest.MonkeyPatch) -> None:
    c1 = _FakeContainer(container_id="a" * 64, name="web-api", image_tags=["nginx:latest"])
    c2 = _FakeContainer(container_id="b" * 64, name="cache", image_tags=[])  # empty tags

    fake_client = MagicMock()
    fake_client.containers.list.return_value = [c1, c2]
    monkeypatch.setattr("docker.from_env", lambda: fake_client)

    records = list_running_containers()

    assert len(records) == 2
    assert all(isinstance(r, ContainerRecord) for r in records)
    assert records[0].name == "web-api"
    assert records[0].short_id == "a" * 12
    assert records[0].image == "nginx:latest"
    # Empty tag list falls back to <none>:<none>
    assert records[1].image == "<none>:<none>"
    fake_client.containers.list.assert_called_once_with(filters={"status": "running"})


def test_probe_available_shells_returns_only_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """probe_available_shells invokes `command -v` once per shell; returns installed ones."""
    fake_container = MagicMock()

    # 0 = found, 1 = not found. Probe order is sh, bash, zsh (per impl).
    def _exec_run(cmd, demux=False):
        shell = cmd[-1].rsplit(" ", 1)[-1]
        return (0, b"/bin/x\n") if shell in {"sh", "bash"} else (1, b"")

    fake_container.exec_run.side_effect = _exec_run

    fake_client = MagicMock()
    fake_client.containers.get.return_value = fake_container
    monkeypatch.setattr("docker.from_env", lambda: fake_client)

    result = probe_available_shells("abcd1234")

    assert result == ["sh", "bash"]


def test_probe_available_shells_returns_sh_fallback_on_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = MagicMock()
    fake_client.containers.get.side_effect = docker.errors.APIError("boom")
    monkeypatch.setattr("docker.from_env", lambda: fake_client)

    assert probe_available_shells("abcd1234") == ["sh"]


def test_enter_container_calls_execvp_with_correct_args(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_execvp = MagicMock()
    monkeypatch.setattr("os.execvp", mock_execvp)

    enter_container("abcd1234", "bash")

    mock_execvp.assert_called_once_with("docker", ["docker", "exec", "-it", "abcd1234", "bash"])


def test_enter_container_rejects_shell_outside_allow_list(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_execvp = MagicMock()
    monkeypatch.setattr("os.execvp", mock_execvp)

    with pytest.raises(CLIError) as exc_info:
        enter_container("abcd1234", "fish")

    assert exc_info.value.exit_code == ExitCode.SHELL_UNAVAILABLE
    mock_execvp.assert_not_called()


def test_list_running_containers_handles_bad_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid StartedAt should not crash; falls back to now()."""
    c = _FakeContainer(container_id="c" * 64, name="odd", image_tags=["alpine"], started_at="not-an-isoformat")
    fake_client = SimpleNamespace(containers=SimpleNamespace(list=lambda filters: [c]))
    monkeypatch.setattr("docker.from_env", lambda: fake_client)

    records = list_running_containers()

    assert len(records) == 1
    assert records[0].name == "odd"
