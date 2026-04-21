from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import structlog

from pyocker_enter.logging_config import configure_logging, suspend_console_logging


def _count_stderr_handlers() -> int:
    root = logging.getLogger()
    return len([
        h for h in root.handlers if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr
    ])


def test_file_handler_writes_json_lines(tmp_path: Path) -> None:
    """configure_logging must write valid JSON lines to the log file."""
    log_file = tmp_path / "app.log"
    configure_logging(log_file=log_file)

    logger = structlog.get_logger("test")
    logger.info("hello", key="value")

    lines = [line for line in log_file.read_text().splitlines() if line.strip()]
    assert lines, "log file must not be empty"
    parsed = json.loads(lines[-1])
    assert parsed.get("event") == "hello"
    assert parsed.get("key") == "value"
    assert parsed.get("level") == "info"
    assert "timestamp" in parsed


def test_suspend_console_logging_detaches_stderr(tmp_path: Path) -> None:
    """suspend_console_logging must remove stderr handler and restore it on exit."""
    configure_logging(log_file=tmp_path / "app.log")

    before = _count_stderr_handlers()
    assert before >= 1, "expected at least one stderr handler after configure_logging"

    with suspend_console_logging():
        during = _count_stderr_handlers()
        assert during == 0, f"expected 0 stderr handlers during suspension, got {during}"

    after = _count_stderr_handlers()
    assert after == before, f"expected {before} stderr handlers restored, got {after}"


def test_suspend_console_logging_no_op_when_no_stderr_handler(tmp_path: Path) -> None:
    """suspend_console_logging must be safe even if called with no stderr handler."""
    # Reset root logger to have no handlers
    root = logging.getLogger()
    root.handlers.clear()

    # Should not raise
    with suspend_console_logging():
        pass
