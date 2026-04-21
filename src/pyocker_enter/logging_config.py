from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import structlog


def configure_logging(log_file: Path | None = None) -> None:
    """Configure structlog with rotating JSON file handler and optional console handler."""
    if log_file is None:
        env_path = os.environ.get("PYOCKER_LOG_FILE")
        if env_path:
            log_file = Path(env_path)
        else:
            log_file = Path.home() / ".local" / "state" / "pyocker-enter" / "pyocker-enter.log"

    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Shared pre-chain processors (run before rendering)
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # File handler — always JSON
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )
    file_handler.setFormatter(file_formatter)

    # Console handler — ConsoleRenderer unless LOG_FORMAT=json
    log_format = os.environ.get("LOG_FORMAT", "pretty").lower()
    console_processor: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if log_format == "json" else structlog.dev.ConsoleRenderer()
    )

    console_handler = logging.StreamHandler(sys.stderr)
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=console_processor,
        foreign_pre_chain=shared_processors,
    )
    console_handler.setFormatter(console_formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.DEBUG)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


@contextmanager
def suspend_console_logging() -> Generator[None, None, None]:
    """Detach the stderr StreamHandler while the TUI owns the terminal.

    Prevents structlog's ConsoleRenderer from writing ANSI escape sequences
    on top of Textual's display. Re-attaches handlers on exit.
    """
    root = logging.getLogger()
    stderr_handlers = [
        h for h in root.handlers if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr
    ]
    for h in stderr_handlers:
        root.removeHandler(h)
    try:
        yield
    finally:
        for h in stderr_handlers:
            root.addHandler(h)
