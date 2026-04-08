from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select, Static, TextArea

from anne.models import Idea

_EDITABLE_FIELDS = [
    "raw_quote",
    "raw_note",
    "raw_ref",
    "reviewed_quote",
    "reviewed_comment",
    "presentation_text",
    "rejection_reason",
    "tags",
]


class EditFieldModal(ModalScreen[tuple[str, str] | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save", show=False, priority=True),
    ]

    DEFAULT_CSS = """
    EditFieldModal {
        align: center middle;
    }

    EditFieldModal > Vertical {
        width: 80;
        height: auto;
        max-height: 30;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    EditFieldModal Label {
        width: 100%;
        margin-bottom: 1;
    }

    EditFieldModal Select {
        width: 100%;
        margin-bottom: 1;
    }

    EditFieldModal TextArea {
        height: 10;
        margin-bottom: 1;
    }

    EditFieldModal Button {
        margin: 0 1;
    }

    EditFieldModal .hint {
        color: $text-muted;
        width: 100%;
    }
    """

    def __init__(self, idea: Idea, preset_field: str | None = None) -> None:
        super().__init__()
        self._idea = idea
        self._preset_field = preset_field

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[bold]Edit Idea #{self._idea.id}[/bold]")
            if self._preset_field:
                yield Label(f"Field: [cyan]{self._preset_field}[/cyan]")
            else:
                yield Select(
                    [(f, f) for f in _EDITABLE_FIELDS],
                    id="field-select",
                    prompt="Select field",
                    value=_EDITABLE_FIELDS[0],
                )
            current_value = self._get_current_value(self._preset_field or _EDITABLE_FIELDS[0])
            yield TextArea(current_value, id="value-input")
            with Horizontal():
                yield Button("Save", variant="success", id="save-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")
            yield Static(
                "Ctrl+S to save, Esc to cancel.",
                classes="hint",
            )

    def _get_current_value(self, field: str) -> str:
        value = getattr(self._idea, field, None)
        if value is None:
            return ""
        return str(value)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "field-select" and event.value is not Select.BLANK:
            text_area = self.query_one("#value-input", TextArea)
            text_area.clear()
            text_area.insert(self._get_current_value(str(event.value)))

    def action_save(self) -> None:
        if self._preset_field:
            field = self._preset_field
        else:
            select = self.query_one("#field-select", Select)
            field = str(select.value)
        text_area = self.query_one("#value-input", TextArea)
        self.dismiss((field, text_area.text))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self.action_save()
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
