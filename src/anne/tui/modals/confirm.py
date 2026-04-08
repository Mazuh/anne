from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, TextArea


class ConfirmModal(ModalScreen[tuple[bool, str]]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "confirm", "Confirm", show=False, priority=True),
    ]

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }

    ConfirmModal > Vertical {
        width: 60;
        height: auto;
        max-height: 20;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    ConfirmModal Label {
        width: 100%;
        margin-bottom: 1;
    }

    ConfirmModal TextArea {
        height: 5;
        margin-bottom: 1;
    }

    ConfirmModal Button {
        margin: 0 1;
    }
    """

    def __init__(self, message: str, show_reason: bool = False) -> None:
        super().__init__()
        self._message = message
        self._show_reason = show_reason

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._message)
            if self._show_reason:
                yield TextArea(id="reason-input")
                yield Label("[dim]Optional reason (Ctrl+S to confirm, Esc to cancel)[/dim]")
            with Horizontal():
                yield Button("Confirm", variant="error", id="confirm-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def _do_confirm(self) -> None:
        reason = ""
        if self._show_reason:
            reason = self.query_one("#reason-input", TextArea).text.strip()
        self.dismiss((True, reason))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-btn":
            self._do_confirm()
        else:
            self.dismiss((False, ""))

    def action_confirm(self) -> None:
        self._do_confirm()

    def action_cancel(self) -> None:
        self.dismiss((False, ""))
