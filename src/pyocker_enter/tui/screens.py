from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView


class ShellPickerModal(ModalScreen[str | None]):
    """Modal presenting the caller with a list of installed shells.

    Resolves with the selected shell name, or with ``None`` if the user
    cancels via ``escape``.
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    ShellPickerModal {
        align: center middle;
    }
    ShellPickerModal > Vertical {
        width: 40;
        height: auto;
        padding: 1 2;
        background: $panel;
        border: round $accent;
    }
    ShellPickerModal Label {
        padding-bottom: 1;
    }
    """

    def __init__(self, available: list[str]) -> None:
        super().__init__()
        self._available = list(available)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Pick a shell")
            yield ListView(
                *(ListItem(Label(shell), name=shell) for shell in self._available),
                id="shells",
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.dismiss(event.item.name)

    def action_cancel(self) -> None:
        self.dismiss(None)
