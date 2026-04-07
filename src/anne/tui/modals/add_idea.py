from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, TextArea


class AddIdeaModal(ModalScreen[tuple[str, str, str] | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+enter", "save", "Save", show=False, priority=True),
    ]

    DEFAULT_CSS = """
    AddIdeaModal {
        align: center middle;
    }

    AddIdeaModal > Vertical {
        width: 80;
        height: auto;
        max-height: 40;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    AddIdeaModal Label {
        width: 100%;
    }

    AddIdeaModal .field-label {
        margin-top: 1;
    }

    AddIdeaModal TextArea {
        height: 6;
        margin-bottom: 0;
    }

    AddIdeaModal Input {
        margin-bottom: 0;
    }

    AddIdeaModal Button {
        margin: 0 1;
    }

    AddIdeaModal .hint {
        margin-top: 1;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]Add Idea[/bold]")
            yield Label("Quote", classes="field-label")
            yield TextArea(id="quote-input")
            yield Label("Note", classes="field-label")
            yield TextArea(id="note-input")
            yield Label("Ref", classes="field-label")
            yield Input(id="ref-input")
            with Horizontal():
                yield Button("Save", variant="success", id="save-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")
            yield Static(
                "Fill at least quote or note. Ctrl+Enter to save, Tab to switch fields, Esc to cancel.",
                classes="hint",
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Submit form when Enter is pressed in the ref Input field."""
        self.action_save()

    def action_save(self) -> None:
        quote = self.query_one("#quote-input", TextArea).text.strip()
        note = self.query_one("#note-input", TextArea).text.strip()
        if not quote and not note:
            self.notify("At least quote or note is required.", severity="error")
            return
        ref = self.query_one("#ref-input", Input).value.strip()
        self.dismiss((quote, note, ref))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self.action_save()
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
