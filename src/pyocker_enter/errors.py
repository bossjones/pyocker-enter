from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    NO_MATCH = 1
    DAEMON_UNREACHABLE = 2
    SHELL_UNAVAILABLE = 3
    NOT_A_TTY = 4
    USER_CANCELLED = 130  # SIGINT convention


class CLIError(Exception):
    def __init__(self, message: str, exit_code: ExitCode) -> None:
        super().__init__(message)
        self.exit_code = exit_code
