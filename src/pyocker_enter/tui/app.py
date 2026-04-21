from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

import structlog
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Input

from pyocker_enter.docker_utils import (
    ContainerRecord,
    list_running_containers,
    probe_available_shells,
)
from pyocker_enter.fuzzy import rank
from pyocker_enter.tui.screens import ShellPickerModal

log = structlog.get_logger(__name__)

_COLUMNS: tuple[str, ...] = ("ID", "NAME", "IMAGE", "STATUS", "UPTIME")


def _uptime(started_at: datetime) -> str:
    """Human-readable uptime (coarse)."""
    now = datetime.now(tz=timezone.utc)
    delta = now - started_at
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    if secs < 86400:
        return f"{secs // 3600}h"
    return f"{secs // 86400}d"


class ContainerListScreen(Screen[tuple[str, str] | None]):
    """Fuzzy-searchable list of running containers with a shell picker on submit."""

    BINDINGS: ClassVar = [
        Binding("escape", "app.quit", "Quit"),
    ]

    def __init__(
        self,
        records: list[ContainerRecord] | None = None,
        *,
        shell_probe: Callable[[str], list[str]] = probe_available_shells,
    ) -> None:
        super().__init__()
        self._injected = records
        self._shell_probe = shell_probe
        self._all: list[ContainerRecord] = []
        self._visible: list[ContainerRecord] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Input(placeholder="fuzzy search…", id="search")
            yield DataTable(id="containers", cursor_type="row")
            yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#containers", DataTable)
        table.add_columns(*_COLUMNS)
        self._all = self._injected if self._injected is not None else list_running_containers()
        self._populate(self._all)

    def _populate(self, records: list[ContainerRecord]) -> None:
        table = self.query_one("#containers", DataTable)
        table.clear()
        for rec in records:
            table.add_row(
                rec.short_id,
                rec.name,
                rec.image,
                rec.status,
                _uptime(rec.started_at),
                key=rec.id,
            )
        self._visible = list(records)

    def on_input_changed(self, event: Input.Changed) -> None:
        self._populate(rank(event.value, self._all))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        rec = next((r for r in self._visible if r.id == row_key), None)
        if rec is None:
            return

        log.info("containers.selected", container_id=rec.id, name=rec.name)
        available = self._shell_probe(rec.id)
        if len(available) <= 1:
            chosen = available[0] if available else "sh"
            self.app.exit(result=(rec.id, chosen))
            return

        def _on_picked(shell: str | None) -> None:
            if shell is None:
                return
            self.app.exit(result=(rec.id, shell))

        self.app.push_screen(ShellPickerModal(available), _on_picked)


class PyockerEnterApp(App[tuple[str, str] | None]):
    """Top-level Textual app. Pushes ContainerListScreen on mount."""

    CSS_PATH = Path(__file__).parent / "styles.tcss"
    BINDINGS: ClassVar = [("q", "quit", "Quit"), ("ctrl+c", "quit", "Quit")]

    def __init__(
        self,
        records: list[ContainerRecord] | None = None,
        *,
        shell_probe: Callable[[str], list[str]] = probe_available_shells,
    ) -> None:
        super().__init__()
        self._records = records
        self._shell_probe = shell_probe

    def get_default_screen(self) -> ContainerListScreen:
        return ContainerListScreen(records=self._records, shell_probe=self._shell_probe)
