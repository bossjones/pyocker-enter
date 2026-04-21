from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pyocker_enter.cli import app
from pyocker_enter.docker_utils import (
    enter_container,
    list_running_containers,
    probe_available_shells,
    resolve_container,
)
from pyocker_enter.errors import CLIError, ExitCode


@pytest.mark.integration
def test_list_running_containers_sees_all_three_fixtures(compose_stack: None) -> None:
    """All three fixture containers must appear in list_running_containers."""
    records = list_running_containers()
    names = {r.name for r in records}
    assert "pyocker-test-sh" in names
    assert "pyocker-test-bash" in names
    assert "pyocker-test-zsh" in names


@pytest.mark.integration
def test_probe_available_shells_on_alpine_returns_sh_only(compose_stack: None) -> None:
    """Alpine fixture should have only sh."""
    records = list_running_containers()
    rec = next(r for r in records if r.name == "pyocker-test-sh")
    shells = probe_available_shells(rec.id)
    assert shells == ["sh"]


@pytest.mark.integration
def test_probe_available_shells_on_bash_container(compose_stack: None) -> None:
    """Ubuntu fixture should have sh and bash."""
    records = list_running_containers()
    rec = next(r for r in records if r.name == "pyocker-test-bash")
    shells = set(probe_available_shells(rec.id))
    assert {"sh", "bash"} <= shells
    assert "zsh" not in shells


@pytest.mark.integration
def test_probe_available_shells_on_zsh_container(compose_stack: None) -> None:
    """Ubuntu+zsh fixture should have sh, bash, and zsh."""
    records = list_running_containers()
    rec = next(r for r in records if r.name == "pyocker-test-zsh")
    shells = set(probe_available_shells(rec.id))
    assert {"sh", "bash", "zsh"} <= shells


@pytest.mark.integration
def test_enter_container_builds_correct_execvp_args(compose_stack: None) -> None:
    """enter_container must call os.execvp with the real 64-char container ID."""
    records = list_running_containers()
    rec = next(r for r in records if r.name == "pyocker-test-bash")

    with patch("os.execvp") as mock_execvp:
        enter_container(rec.id, "bash")

    mock_execvp.assert_called_once_with("docker", ["docker", "exec", "-it", rec.id, "bash"])
    assert len(rec.id) == 64, f"expected 64-char id, got {len(rec.id)}"


@pytest.mark.integration
def test_resolve_container_ambiguity_raises_cli_error(compose_stack: None) -> None:
    """An empty query prefix matches every short_id -> must raise CLIError(ambiguous).

    With >= 2 running containers (the three fixtures are present), the empty
    prefix matches every short_id under the unique-prefix precedence step,
    exercising the ambiguity branch end-to-end against the real daemon.
    """
    records = list_running_containers()
    assert len(records) >= 2

    with pytest.raises(CLIError) as exc_info:
        resolve_container("", records)

    assert exc_info.value.exit_code == ExitCode.NO_MATCH
    assert "ambiguous" in str(exc_info.value).lower()


@pytest.mark.integration
def test_tty_guard_refuses_when_stdin_not_tty(compose_stack: None) -> None:
    """CliRunner's stdin is not a TTY -> CLI exits NOT_A_TTY without calling execvp."""
    runner = CliRunner()
    with patch("os.execvp") as mock_execvp:
        result = runner.invoke(app, ["pyocker-test-bash", "--shell", "bash"])

    assert result.exit_code == int(ExitCode.NOT_A_TTY), (
        f"expected NOT_A_TTY ({int(ExitCode.NOT_A_TTY)}), got {result.exit_code}\n"
        f"stdout={result.stdout!r} exc={result.exception!r}"
    )
    mock_execvp.assert_not_called()
