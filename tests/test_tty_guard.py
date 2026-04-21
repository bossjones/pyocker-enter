from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from pyocker_enter.cli import app
from pyocker_enter.errors import ExitCode


def test_cli_refuses_exec_when_stdin_not_a_tty() -> None:
    """CLI must exit with NOT_A_TTY (4) and not call os.execvp when stdin is not a TTY."""
    runner = CliRunner()

    with (
        patch("pyocker_enter.cli.sys.stdin") as mock_stdin,
        patch("pyocker_enter.cli.sys.stdout") as mock_stdout,
        patch("os.execvp") as mock_execvp,
    ):
        mock_stdin.isatty.return_value = False
        mock_stdout.isatty.return_value = True

        result = runner.invoke(app, ["some-container", "--shell", "sh"])

    assert result.exit_code == int(ExitCode.NOT_A_TTY), (
        f"expected exit code {int(ExitCode.NOT_A_TTY)}, got {result.exit_code}\n"
        f"stdout={result.stdout!r}\nexception={result.exception!r}"
    )
    mock_execvp.assert_not_called()


def test_cli_refuses_exec_when_stdout_not_a_tty() -> None:
    """CLI must also refuse when stdout is not a TTY."""
    runner = CliRunner()

    with (
        patch("pyocker_enter.cli.sys.stdin") as mock_stdin,
        patch("pyocker_enter.cli.sys.stdout") as mock_stdout,
        patch("os.execvp") as mock_execvp,
    ):
        mock_stdin.isatty.return_value = True
        mock_stdout.isatty.return_value = False

        result = runner.invoke(app, ["some-container", "--shell", "sh"])

    assert result.exit_code == int(ExitCode.NOT_A_TTY)
    mock_execvp.assert_not_called()
