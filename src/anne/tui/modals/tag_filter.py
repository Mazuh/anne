from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Label, RadioButton, RadioSet, Static


class TagFilterModal(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    TagFilterModal {
        align: center middle;
    }

    TagFilterModal > Vertical {
        width: 40;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    TagFilterModal Label {
        width: 100%;
        margin-bottom: 1;
    }

    TagFilterModal RadioSet {
        width: 100%;
        margin-bottom: 1;
    }

    TagFilterModal .hint {
        color: $text-muted;
        width: 100%;
    }
    """

    def __init__(self, current_tag: str | None, available_tags: list[str]) -> None:
        super().__init__()
        self._current_tag = current_tag
        self._available_tags = available_tags

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]Filter by tag[/bold]")
            if self._available_tags:
                options = ["All"] + self._available_tags
                current_value = self._current_tag or "All"
                yield RadioSet(
                    *[RadioButton(opt, value=(opt == current_value)) for opt in options],
                    id="tag-filter-radio",
                )
                yield Static("Space to select, Enter to apply, Esc to cancel", classes="hint")
            else:
                yield Label("No tags found.")
                yield Static("Esc to close", classes="hint")

    def on_key(self, event: Key) -> None:
        if event.key == "enter" and self._available_tags:
            event.stop()
            event.prevent_default()
            self._apply()

    def _apply(self) -> None:
        radio_set = self.query_one("#tag-filter-radio", RadioSet)
        idx = radio_set.pressed_index
        if idx is None or idx == 0:
            self.dismiss(None)
        else:
            self.dismiss(self._available_tags[idx - 1])

    def action_cancel(self) -> None:
        self.dismiss(self._current_tag)
