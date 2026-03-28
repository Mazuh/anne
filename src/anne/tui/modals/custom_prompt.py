from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static, TextArea


class CustomPromptModal(ModalScreen[str | None]):
    BINDINGS = [
        Binding("enter", "submit", "Submit", show=False, priority=True),
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    CustomPromptModal {
        align: center middle;
    }

    CustomPromptModal > Vertical {
        width: 80;
        height: auto;
        max-height: 25;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    CustomPromptModal Label {
        width: 100%;
        margin-bottom: 1;
    }

    CustomPromptModal TextArea {
        height: 8;
        margin-bottom: 1;
    }

    CustomPromptModal Button {
        margin: 0 1;
    }

    CustomPromptModal .hint {
        color: $text-muted;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]AI Prompt[/bold]")
            yield Label(
                "[dim]Ask a question about this idea."
                " This is read-only — nothing will be changed.[/dim]"
            )
            yield TextArea(id="prompt-input")
            with Horizontal():
                yield Button("Submit", variant="success", id="submit-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")
            yield Static(
                "Enter to submit, Shift+Enter for line break, Esc to cancel",
                classes="hint",
            )

    def action_submit(self) -> None:
        self._submit()

    def _submit(self) -> None:
        text_area = self.query_one("#prompt-input", TextArea)
        text = text_area.text.strip()
        if not text:
            self.notify("Prompt cannot be empty.", severity="warning")
            return
        self.dismiss(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit-btn":
            self._submit()
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
