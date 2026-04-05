from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

from anne import APP_AUTHOR, APP_DESCRIPTION, APP_REPO


class AboutModal(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("enter", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    AboutModal {
        align: center middle;
    }

    AboutModal > Vertical {
        width: 64;
        height: auto;
        max-height: 16;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    AboutModal Label {
        width: 100%;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]Anne[/bold]")
            yield Label(APP_DESCRIPTION)
            yield Label(f"[dim]By {APP_AUTHOR}[/dim]")
            yield Label(f"[dim]Source: {APP_REPO}[/dim]")
            yield Label("[dim]Press Esc to close[/dim]")
