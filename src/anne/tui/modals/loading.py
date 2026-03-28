from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label


class LoadingModal(ModalScreen[None]):
    BINDINGS = []

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
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]Calling LLM...[/bold]")
