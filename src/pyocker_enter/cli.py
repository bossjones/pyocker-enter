from __future__ import annotations

import sys
from typing import Annotated

import click
import docker.errors
import typer

from pyocker_enter.docker_utils import (
    enter_container,
    list_running_containers,
    probe_available_shells,
    resolve_container,
)
from pyocker_enter.errors import CLIError, ExitCode
from pyocker_enter.logging_config import configure_logging, suspend_console_logging
from pyocker_enter.tui.app import PyockerEnterApp

_NOT_A_TTY_MESSAGE = "stdin/stdout is not a TTY; docker exec -it requires a real terminal"
_DAEMON_UNREACHABLE_MESSAGE = (
    "could not reach the docker daemon. Is it running? Check DOCKER_HOST or start Docker Desktop / dockerd."
)
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


def _run_direct_exec(container: str, shell: str | None) -> None:
    _require_tty()
    records = list_running_containers()
    rec = resolve_container(container, records)

    chosen = shell or _pick_default_shell(probe_available_shells(rec.id))
    enter_container(rec.id, chosen)


def _run_tui() -> None:
    with suspend_console_logging():
        result = PyockerEnterApp().run()

    if result is None:
        return

    container_id, chosen_shell = result
    _require_tty()
    enter_container(container_id, chosen_shell)


def main(
    container: Annotated[
        str | None,
        typer.Argument(help="Container name, short-id, or unique short-id prefix"),
    ] = None,
    shell: Annotated[
        str | None,
        typer.Option(
            "--shell",
            "-s",
            help="Shell to exec into (sh|bash|zsh). Omit to probe and default to bash.",
            click_type=_SHELL_CHOICES,
        ),
    ] = None,
) -> None:
    """Interactive TUI for entering running Docker containers.

    With no arguments, launches a fuzzy-search TUI listing running containers.
    Given a container name/id, execs straight in (after probing installed
    shells if --shell is omitted).

    Env vars: PYOCKER_LOG_FILE, LOG_FORMAT=json|pretty.
    """
    configure_logging()

    try:
        if container is not None:
            _run_direct_exec(container, shell)
        else:
            _run_tui()
    except CLIError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=int(exc.exit_code)) from exc
    except docker.errors.DockerException as exc:
        typer.echo(f"{_DAEMON_UNREACHABLE_MESSAGE} ({exc})", err=True)
        raise typer.Exit(code=int(ExitCode.DAEMON_UNREACHABLE)) from exc


app = typer.Typer(no_args_is_help=False, add_completion=False)
app.command()(main)
