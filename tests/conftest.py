from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from pyocker_enter.docker_utils import ContainerRecord


@pytest.fixture
def make_record():
    def _make(
        name: str,
        short_id: str = "abcdef123456",
        image: str = "test:latest",
        status: str = "running",
        full_id: str | None = None,
    ) -> ContainerRecord:
        return ContainerRecord(
            id=full_id or (short_id + "0" * (64 - len(short_id))),
            short_id=short_id,
            name=name,
            image=image,
            status=status,
            started_at=datetime.now(tz=timezone.utc),
        )

    return _make


@pytest.fixture
def fake_records(make_record) -> list[ContainerRecord]:
    return [
        make_record("web-api", "aaaaaaaaaaaa", image="nginx:latest"),
        make_record("web-db", "bbbbbbbbbbbb", image="postgres:16"),
        make_record("cache", "cccccccccccc", image="redis:7"),
    ]


@pytest.fixture
def tmp_log_file(tmp_path: Path) -> Path:
    return tmp_path / "pyocker-enter.log"
