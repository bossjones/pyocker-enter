from __future__ import annotations

from typing import Any

import pytest
from textual.app import App, ComposeResult

from pyocker_enter.tui.screens import ShellPickerModal


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
