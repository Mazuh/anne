import subprocess
import sys

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class PromptResponseModal(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close"),
    ]

    DEFAULT_CSS = """
    PromptResponseModal {
        align: center middle;
    }

    PromptResponseModal > Vertical {
        width: 90;
        height: auto;
        max-height: 30;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    PromptResponseModal Label {
        width: 100%;
        margin-bottom: 1;
    }

    PromptResponseModal VerticalScroll {
        height: auto;
        max-height: 20;
        margin-bottom: 1;
    }

    PromptResponseModal Button {
        margin: 0 1;
    }
    """

    def __init__(self, response: str) -> None:
        super().__init__()
        self._response = response

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]AI Response[/bold]")
            with VerticalScroll():
                yield Static(self._response, id="response-text")
            with Horizontal():
                if sys.platform == "darwin":
                    yield Button("Copy", variant="primary", id="copy-btn")
                yield Button("Close", variant="default", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy-btn":
            try:
                subprocess.run(
                    ["pbcopy"],
                    input=self._response.encode(),
                    check=True,
                )
                self.notify("Copied response to clipboard.")
            except (FileNotFoundError, subprocess.CalledProcessError):
                self.notify("Failed to copy to clipboard.", severity="error")
        elif event.button.id == "close-btn":
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
