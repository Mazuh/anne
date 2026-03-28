from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, RadioButton, RadioSet, Static

from anne.models import Idea

_COPYABLE_FIELDS: list[tuple[str, str]] = [
    ("raw_quote", "Raw quote"),
    ("raw_note", "Raw note"),
    ("raw_ref", "Reference"),
    ("reviewed_quote", "Reviewed quote"),
    ("reviewed_comment", "Reviewed comment"),
    ("quick_context", "Quick context"),
    ("presentation_text", "Caption"),
    ("tags", "Tags"),
]


class CopyFieldModal(ModalScreen[str | None]):
    BINDINGS = [
        Binding("enter", "submit", "Copy", show=False, priority=True),
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    CopyFieldModal {
        align: center middle;
    }

    CopyFieldModal > Vertical {
        width: 55;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    CopyFieldModal Label {
        width: 100%;
        margin-bottom: 1;
    }

    CopyFieldModal RadioSet {
        width: 100%;
        margin-bottom: 1;
    }

    CopyFieldModal .hint {
        color: $text-muted;
        width: 100%;
    }
    """

    def __init__(self, idea: Idea) -> None:
        super().__init__()
        self._fields: list[tuple[str, str]] = []
        for attr, label in _COPYABLE_FIELDS:
            value = getattr(idea, attr, None)
            if value:
                self._fields.append((attr, label))

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]Copy field to clipboard[/bold]")
            if not self._fields:
                yield Static("No fields with content to copy.")
            else:
                yield RadioSet(
                    *[
                        RadioButton(label, value=(i == 0))
                        for i, (_attr, label) in enumerate(self._fields)
                    ],
                    id="copy-radio",
                )
            yield Static("Space to select, Enter to copy, Esc to cancel", classes="hint")

    def action_submit(self) -> None:
        if not self._fields:
            self.dismiss(None)
            return
        radio_set = self.query_one("#copy-radio", RadioSet)
        idx = radio_set.pressed_index
        if idx is not None and idx < len(self._fields):
            self.dismiss(self._fields[idx][0])
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
