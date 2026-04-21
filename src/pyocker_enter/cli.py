from __future__ import annotations

import sys
from typing import Annotated

import click
import typer

from pyocker_enter.docker_utils import (
    enter_container,
    list_running_containers,
    probe_available_shells,
    resolve_container,
)
from pyocker_enter.errors import CLIError, ExitCode
from pyocker_enter.logging_config import configure_logging

_NOT_A_TTY_MESSAGE = "stdin/stdout is not a TTY; docker exec -it requires a real terminal"
_SHELL_CHOICES = click.Choice(["sh", "bash", "zsh"])


def _require_tty() -> None:
    """Raise CLIError if stdin or stdout is not a TTY."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise CLIError(_NOT_A_TTY_MESSAGE, ExitCode.NOT_A_TTY)


def _pick_default_shell(available: list[str]) -> str:
    """Prefer bash when installed, else sh, else the first available shell."""
    for preferred in ("bash", "sh"):
        if preferred in available:
            return preferred
    return available[0]


def main(
    container: Annotated[
        str | None,
        typer.Argument(help="Container name, short-id, or unique short-id prefix"),
    ] = None,
    shell: Annotated[
        str | None,
        typer.Option("--shell", "-s", help="Shell to exec into (sh|bash|zsh)", click_type=_SHELL_CHOICES),
    ] = None,
) -> None:
    """Interactive TUI for entering running Docker containers.

    With no arguments, launches a fuzzy-search TUI listing running containers.
    Given a container name/id, execs straight in (after a shell picker if
    --shell is omitted).
    """
    configure_logging()

    if container is not None:
        # Fail fast on non-TTY invocation — docker exec -it would reject anyway.
        try:
            _require_tty()
        except CLIError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=int(exc.exit_code)) from exc

        try:
            records = list_running_containers()
            rec = resolve_container(container, records)
        except CLIError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=int(exc.exit_code)) from exc

        chosen = shell
        if chosen is None:
            available = probe_available_shells(rec.id)
            chosen = _pick_default_shell(available)

        try:
            enter_container(rec.id, chosen)
        except CLIError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=int(exc.exit_code)) from exc
    else:
        # TUI path: stub until Step G wires it up.
        typer.echo("[stub] TUI not yet implemented")


app = typer.Typer(no_args_is_help=False, add_completion=False)
app.command()(main)
