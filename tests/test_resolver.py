from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pyocker_enter.docker_utils import ContainerRecord, resolve_container
from pyocker_enter.errors import CLIError, ExitCode


def _make_record(name: str, short_id: str, full_id: str | None = None) -> ContainerRecord:
    return ContainerRecord(
        id=full_id or (short_id + "a" * (64 - len(short_id))),
        short_id=short_id,
        name=name,
        image="test:latest",
        status="running",
        started_at=datetime.now(tz=timezone.utc),
    )


def test_exact_name_wins_over_prefix_id() -> None:
    """Exact name match takes priority over a short_id that starts with same chars."""
    records = [
        _make_record("web-api", "webabc123456"),
        _make_record("cache", "abc123456789"),
    ]
    result = resolve_container("web-api", records)
    assert result.name == "web-api"


def test_exact_short_id_match() -> None:
    """Query matching 12-char short_id returns that record."""
    records = [
        _make_record("alpha", "aaaaaaaaaaaa"),
        _make_record("beta", "bbbbbbbbbbbb"),
    ]
    result = resolve_container("aaaaaaaaaaaa", records)
    assert result.name == "alpha"


def test_prefix_id_match() -> None:
    """A unique prefix of short_id resolves to the matching record."""
    records = [
        _make_record("alpha", "aaaaaaaaaaaa"),
        _make_record("beta", "bbbbbbbbbbbb"),
    ]
    result = resolve_container("aaaa", records)
    assert result.name == "alpha"


def test_ambiguous_prefix_raises_cli_error() -> None:
    """Two containers whose short_ids share the same prefix -> CLIError(NO_MATCH)."""
    records = [
        _make_record("app-one", "abc111111111"),
        _make_record("app-two", "abc222222222"),
    ]
    with pytest.raises(CLIError) as exc_info:
        resolve_container("abc", records)
    assert exc_info.value.exit_code == ExitCode.NO_MATCH
    assert "ambiguous" in str(exc_info.value).lower()


def test_no_match_raises_cli_error() -> None:
    """Unknown query raises CLIError(NO_MATCH)."""
    records = [_make_record("alpha", "aaaaaaaaaaaa")]
    with pytest.raises(CLIError) as exc_info:
        resolve_container("zzz-does-not-exist", records)
    assert exc_info.value.exit_code == ExitCode.NO_MATCH
