from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

from pyocker_enter.errors import CLIError, ExitCode

if TYPE_CHECKING:
    pass

log = structlog.get_logger(__name__)

ALLOWED_SHELLS: frozenset[str] = frozenset({"sh", "bash", "zsh"})


@dataclass(frozen=True)
class ContainerRecord:
    id: str
    short_id: str
    name: str
    image: str
    status: str
    started_at: datetime


def list_running_containers() -> list[ContainerRecord]:
    """Return running containers via the docker SDK."""
    import docker

    client = docker.from_env()
    containers = client.containers.list(filters={"status": "running"})
    records = []
    for c in containers:
        tags = c.image.tags
        image = tags[0] if tags else "<none>:<none>"
        started_raw = c.attrs.get("State", {}).get("StartedAt", "")
        try:
            started_at = datetime.fromisoformat(started_raw.rstrip("Z")).replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            started_at = datetime.now(tz=timezone.utc)
        records.append(
            ContainerRecord(
                id=c.id,
                short_id=c.id[:12],
                name=c.name,
                image=image,
                status=c.status,
                started_at=started_at,
            )
        )
    log.info("containers.listed", count=len(records))
    return records


def resolve_container(query: str, records: list[ContainerRecord]) -> ContainerRecord:
    """Resolve a container by name or ID with explicit precedence.

    Precedence: exact name -> exact short_id -> exact full_id -> unique short_id prefix -> error.
    """
    # 1. Exact name match
    for r in records:
        if r.name == query:
            return r

    # 2. Exact short_id match (12 chars)
    for r in records:
        if r.short_id == query:
            return r

    # 3. Exact full_id match
    for r in records:
        if r.id == query:
            return r

    # 4. Unique prefix of short_id
    matches = [r for r in records if r.short_id.startswith(query)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        candidates = ", ".join(r.name for r in matches)
        msg = f"ambiguous query {query!r} matches multiple containers: {candidates}"
        raise CLIError(msg, ExitCode.NO_MATCH)

    msg = f"no running container matches {query!r}"
    raise CLIError(msg, ExitCode.NO_MATCH)


def probe_available_shells(container_id: str) -> list[str]:
    """Return shells installed in the container (subset of ALLOWED_SHELLS).

    Probes each shell individually because `command -v sh bash zsh` in dash
    stops emitting output after the first missing shell, silently dropping
    shells that follow it in the argument list.
    """
    import docker  # noqa: PLC0415
    import docker.errors  # noqa: PLC0415

    client = docker.from_env()
    try:
        container = client.containers.get(container_id)
        found = []
        for shell in ("sh", "bash", "zsh"):
            exit_code, _ = container.exec_run(f"command -v {shell}", demux=False)
            if exit_code == 0:
                found.append(shell)
        return found or ["sh"]
    except (docker.errors.APIError, docker.errors.DockerException) as exc:
        log.warning("probe_shells.failed", container_id=container_id, error=str(exc))
        return ["sh"]


def enter_container(container_id: str, shell: str) -> None:
    """Replace the Python process with docker exec -it <id> <shell>."""
    if shell not in ALLOWED_SHELLS:
        msg = f"shell {shell!r} is not in allow-list {sorted(ALLOWED_SHELLS)}"
        raise CLIError(msg, ExitCode.SHELL_UNAVAILABLE)
    log.info("exec.invoked", container_id=container_id, shell=shell)
    os.execvp("docker", ["docker", "exec", "-it", container_id, shell])  # noqa: S606, S607
