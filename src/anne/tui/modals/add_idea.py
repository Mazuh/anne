from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static, TextArea


class AddIdeaModal(ModalScreen[tuple[str, str, str] | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
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

    AddIdeaModal #ref-input {
        height: 3;
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
            yield TextArea(id="ref-input")
            with Horizontal():
                yield Button("Save", variant="success", id="save-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")
            yield Static("Fill at least quote or note. Tab to switch fields, Esc to cancel.", classes="hint")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            quote = self.query_one("#quote-input", TextArea).text.strip()
            note = self.query_one("#note-input", TextArea).text.strip()
            if not quote and not note:
                self.notify("At least quote or note is required.", severity="error")
                return
            ref = self.query_one("#ref-input", TextArea).text.strip()
            self.dismiss((quote, note, ref))
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
