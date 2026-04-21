from __future__ import annotations

from unittest.mock import patch

import pytest

from pyocker_enter.docker_utils import enter_container, list_running_containers, probe_available_shells


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
