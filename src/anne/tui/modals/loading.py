from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class LoadingModal(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    LoadingModal {
        align: center middle;
    }

    LoadingModal > Vertical {
        width: 40;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    LoadingModal Label {
        width: 100%;
        text-align: center;
    }

    LoadingModal .hint {
        color: $text-muted;
        width: 100%;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]Calling LLM...[/bold]")
            yield Static("Esc to cancel", classes="hint")

    def action_cancel(self) -> None:
        self.dismiss(False)
