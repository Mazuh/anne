import subprocess
import sys

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class PromptResponseModal(ModalScreen[bool | None]):
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("r", "retry", "Retry"),
        *(
            [Binding("c", "copy", "Copy", show=False)]
            if sys.platform == "darwin"
            else []
        ),
    ]

    DEFAULT_CSS = """
    PromptResponseModal {
        align: center middle;
    }

    PromptResponseModal > Vertical {
        width: 90;
        height: auto;
        max-height: 35;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    PromptResponseModal Label {
        width: 100%;
        margin-bottom: 1;
    }

    PromptResponseModal #prompt-label {
        color: $text-muted;
        width: 100%;
        max-height: 3;
        overflow-y: hidden;
        text-overflow: ellipsis;
        margin-bottom: 1;
    }

    PromptResponseModal VerticalScroll {
        height: auto;
        max-height: 22;
        margin-bottom: 1;
    }

    PromptResponseModal Button {
        margin: 0 1;
    }

    PromptResponseModal .hint {
        color: $text-muted;
        width: 100%;
    }
    """

    def __init__(self, response: str, prompt: str = "") -> None:
        super().__init__()
        self._response = response
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]AI Response[/bold]")
            if self._prompt:
                yield Static(
                    f"[dim]Prompt: {self._prompt}[/dim]", id="prompt-label"
                )
            with VerticalScroll():
                yield Static(self._response, id="response-text")
            with Horizontal():
                if sys.platform == "darwin":
                    yield Button("Copy", variant="primary", id="copy-btn")
                yield Button("Retry", variant="warning", id="retry-btn")
                yield Button("Close", variant="default", id="close-btn")
            if sys.platform == "darwin":
                yield Static(
                    "c to copy, r to retry, Esc to close", classes="hint"
                )
            else:
                yield Static("r to retry, Esc to close", classes="hint")

    def action_copy(self) -> None:
        if sys.platform != "darwin":
            return
        try:
            subprocess.run(
                ["pbcopy"],
                input=self._response.encode(),
                check=True,
            )
            self.notify("Copied response to clipboard.")
        except (FileNotFoundError, subprocess.CalledProcessError):
            self.notify("Failed to copy to clipboard.", severity="error")

    def action_retry(self) -> None:
        self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy-btn":
            self.action_copy()
        elif event.button.id == "retry-btn":
            self.action_retry()
        elif event.button.id == "close-btn":
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
