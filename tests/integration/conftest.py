from __future__ import annotations

import shutil
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest

COMPOSE_FILE = Path(__file__).parent / "docker-compose.yml"


def _docker_bin() -> str:
    """Return the absolute path to the docker binary, or skip if not installed."""
    path = shutil.which("docker")
    if path is None:
        pytest.skip("docker binary not found on PATH")
    return path


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-apply integration marker to all tests in the integration directory."""
    integration_dir = Path(__file__).parent
    for item in items:
        if item.fspath and Path(item.fspath).is_relative_to(integration_dir):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def compose_stack() -> Generator[None, None, None]:
    """Session-scoped fixture: start docker compose stack, yield, tear down."""
    docker = _docker_bin()

    # Skip if docker daemon is not available
    result = subprocess.run(  # noqa: S603
        [docker, "version"],
        capture_output=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("docker daemon not available")

    # Pull images first to avoid healthcheck races on slow links
    subprocess.run(  # noqa: S603
        [docker, "compose", "-f", str(COMPOSE_FILE), "pull"],
        check=True,
        timeout=300,
    )

    # Start the stack and wait for healthchecks
    subprocess.run(  # noqa: S603
        [docker, "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--wait"],
        check=True,
        timeout=180,
    )

    yield

    # Tear down
    subprocess.run(  # noqa: S603
        [docker, "compose", "-f", str(COMPOSE_FILE), "down", "-v"],
        check=True,
        timeout=60,
    )
