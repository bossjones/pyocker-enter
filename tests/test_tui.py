from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from pyocker_enter.docker_utils import ContainerRecord
from pyocker_enter.tui.app import PyockerEnterApp
from pyocker_enter.tui.screens import ShellPickerModal


def _rec(name: str, short: str, image: str = "nginx:latest") -> ContainerRecord:
    return ContainerRecord(
        id=short + "0" * (64 - len(short)),
        short_id=short,
        name=name,
        image=image,
        status="running",
        started_at=datetime.now(tz=timezone.utc),
    )


class _PickerHarness(App[str | None]):
    """Tiny App that pushes ShellPickerModal on mount and exits with the result."""

    def __init__(self, available: list[str]) -> None:
        super().__init__()
        self._available = available
        self.captured: Any = object()  # sentinel

    def compose(self) -> ComposeResult:  # pragma: no cover - empty shell
        return iter(())

    def on_mount(self) -> None:
        def _on_dismiss(result: str | None) -> None:
            self.captured = result
            self.exit(result)

        self.push_screen(ShellPickerModal(self._available), _on_dismiss)


@pytest.mark.asyncio
async def test_shell_picker_returns_selected_shell() -> None:
    """down + enter on the 3-shell modal should return the second item (bash)."""
    app = _PickerHarness(["sh", "bash", "zsh"])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down", "enter")
        await pilot.pause()
    assert app.captured == "bash"


@pytest.mark.asyncio
async def test_shell_picker_escape_returns_none() -> None:
    app = _PickerHarness(["sh", "bash"])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.captured is None


@pytest.mark.asyncio
async def test_container_list_filters_on_input_change() -> None:
    """Typing 'web' must reduce the DataTable to the two web-* containers."""
    records = [
        _rec("web-api", "aaaaaaaaaaaa"),
        _rec("web-db", "bbbbbbbbbbbb", image="postgres:16"),
        _rec("cache", "cccccccccccc", image="redis:7"),
    ]
    app = PyockerEnterApp(records=records)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.query_one("#containers", DataTable)
        assert table.row_count == 3

        from textual.widgets import Input
        search = app.query_one("#search", Input)
        search.value = "web"
        await pilot.pause()
        await pilot.pause()

        table = app.query_one("#containers", DataTable)
        assert table.row_count == 2
        # Confirm only web-* entries remain
        names = {
            table.get_row_at(i)[1] for i in range(table.row_count)
        }
        assert names == {"web-api", "web-db"}
