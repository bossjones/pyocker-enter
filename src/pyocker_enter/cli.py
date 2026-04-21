from __future__ import annotations

import sys
from typing import Annotated

import click
import typer

from pyocker_enter.errors import CLIError, ExitCode

_NOT_A_TTY_MESSAGE = "stdin/stdout is not a TTY; docker exec -it requires a real terminal"
_SHELL_CHOICES = click.Choice(["sh", "bash", "zsh"])


def _require_tty() -> None:
    """Raise CLIError if stdin or stdout is not a TTY."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise CLIError(_NOT_A_TTY_MESSAGE, ExitCode.NOT_A_TTY)


def main(
    container: Annotated[str | None, typer.Argument(help="Container name or ID")] = None,
    shell: Annotated[
        str | None,
        typer.Option("--shell", "-s", help="Shell to exec into", click_type=_SHELL_CHOICES),
    ] = None,
) -> None:
    """Interactive TUI for entering running Docker containers."""
    if container is not None:
        # Direct-exec path: resolve container and exec
        try:
            _require_tty()
        except CLIError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=int(exc.exit_code)) from exc
        # NOTE: Full implementation (list_running_containers, resolve_container,
        # enter_container) is wired in the main implementation tasks.
        typer.echo(f"[stub] would exec into {container!r} with shell {shell!r}")
    else:
        # TUI path: stub until TUI is implemented
        typer.echo("[stub] TUI not yet implemented")


# Expose as a Typer app so the console_script entry point and tests can use it.
app = typer.Typer(no_args_is_help=False, add_completion=False)
app.command()(main)
