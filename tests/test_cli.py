from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from pyocker_enter.cli import app
from pyocker_enter.docker_utils import ContainerRecord
from pyocker_enter.errors import ExitCode


def _record(name: str = "web-api", short: str = "aaaaaaaaaaaa") -> ContainerRecord:
    return ContainerRecord(
        id=short + "0" * (64 - len(short)),
        short_id=short,
        name=name,
        image="nginx:latest",
        status="running",
        started_at=datetime.now(tz=timezone.utc),
    )


def test_cli_direct_exec_skips_tui() -> None:
    """`pyocker-enter <name> --shell bash` must resolve + exec without launching the TUI."""
    rec = _record()
    runner = CliRunner()

    with (
        patch("pyocker_enter.cli.list_running_containers", return_value=[rec]) as mock_list,
        patch("pyocker_enter.cli.enter_container") as mock_enter,
        patch("pyocker_enter.cli._require_tty"),
        patch("pyocker_enter.cli._launch_tui", create=True) as mock_tui,
    ):
        result = runner.invoke(app, ["web-api", "--shell", "bash"])

    assert result.exit_code == 0, f"stdout={result.stdout!r} exc={result.exception!r}"
    mock_list.assert_called_once()
    mock_enter.assert_called_once_with(rec.id, "bash")
    mock_tui.assert_not_called()


def test_cli_direct_exec_no_shell_flag_probes_and_defaults_to_bash() -> None:
    """Without --shell, CLI should probe and prefer bash when installed."""
    rec = _record()
    runner = CliRunner()

    with (
        patch("pyocker_enter.cli.list_running_containers", return_value=[rec]),
        patch("pyocker_enter.cli.probe_available_shells", return_value=["sh", "bash"]),
        patch("pyocker_enter.cli.enter_container") as mock_enter,
        patch("pyocker_enter.cli._require_tty"),
    ):
        result = runner.invoke(app, ["web-api"])

    assert result.exit_code == 0
    mock_enter.assert_called_once_with(rec.id, "bash")


def test_cli_direct_exec_no_shell_flag_falls_back_to_sh() -> None:
    """When probe returns only sh, CLI execs with sh."""
    rec = _record()
    runner = CliRunner()
    with (
        patch("pyocker_enter.cli.list_running_containers", return_value=[rec]),
        patch("pyocker_enter.cli.probe_available_shells", return_value=["sh"]),
        patch("pyocker_enter.cli.enter_container") as mock_enter,
        patch("pyocker_enter.cli._require_tty"),
    ):
        result = runner.invoke(app, ["web-api"])

    assert result.exit_code == 0
    mock_enter.assert_called_once_with(rec.id, "sh")


def test_cli_launches_tui_when_no_container_arg() -> None:
    """With no positional arg, CLI runs the TUI and execs the tuple it returns."""
    runner = CliRunner()

    with (
        patch("pyocker_enter.cli.PyockerEnterApp") as mock_app_cls,
        patch("pyocker_enter.cli.enter_container") as mock_enter,
        patch("pyocker_enter.cli._require_tty"),
    ):
        mock_app_cls.return_value.run.return_value = ("abcd1234" + "0" * 56, "bash")
        result = runner.invoke(app, [])

    assert result.exit_code == 0, f"stdout={result.stdout!r} exc={result.exception!r}"
    mock_app_cls.return_value.run.assert_called_once()
    mock_enter.assert_called_once_with("abcd1234" + "0" * 56, "bash")


def test_cli_tui_returning_none_exits_zero_without_exec() -> None:
    """User cancelling the TUI (q or Ctrl-C) should exit 0 with no execvp."""
    runner = CliRunner()

    with (
        patch("pyocker_enter.cli.PyockerEnterApp") as mock_app_cls,
        patch("pyocker_enter.cli.enter_container") as mock_enter,
        patch("pyocker_enter.cli._require_tty"),
    ):
        mock_app_cls.return_value.run.return_value = None
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    mock_enter.assert_not_called()


def test_cli_direct_exec_daemon_unreachable_exits_two() -> None:
    """If docker.from_env fails, CLI exits with DAEMON_UNREACHABLE (2) and a friendly message."""
    import docker.errors

    runner = CliRunner()
    with (
        patch(
            "pyocker_enter.cli.list_running_containers",
            side_effect=docker.errors.DockerException("Cannot connect"),
        ),
        patch("pyocker_enter.cli.enter_container") as mock_enter,
        patch("pyocker_enter.cli._require_tty"),
    ):
        result = runner.invoke(app, ["whatever", "--shell", "sh"])

    assert result.exit_code == int(ExitCode.DAEMON_UNREACHABLE)
    mock_enter.assert_not_called()
    assert "daemon" in (result.stderr + result.output).lower()


def test_cli_tui_daemon_unreachable_exits_two() -> None:
    """TUI path also surfaces daemon errors as exit 2."""
    import docker.errors

    runner = CliRunner()
    with (
        patch(
            "pyocker_enter.cli.PyockerEnterApp",
            side_effect=docker.errors.DockerException("Cannot connect"),
        ),
        patch("pyocker_enter.cli.enter_container") as mock_enter,
        patch("pyocker_enter.cli._require_tty"),
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == int(ExitCode.DAEMON_UNREACHABLE)
    mock_enter.assert_not_called()


def test_cli_direct_exec_unknown_container_exits_no_match() -> None:
    runner = CliRunner()
    with (
        patch("pyocker_enter.cli.list_running_containers", return_value=[]),
        patch("pyocker_enter.cli.enter_container") as mock_enter,
        patch("pyocker_enter.cli._require_tty"),
    ):
        result = runner.invoke(app, ["ghost-container", "--shell", "sh"])

    assert result.exit_code == int(ExitCode.NO_MATCH)
    mock_enter.assert_not_called()
