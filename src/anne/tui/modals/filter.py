from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Label, RadioButton, RadioSet, Static

from anne.models import IdeaStatus

_STATUS_DESCRIPTIONS: dict[str, str] = {
    "All": "Show all ideas regardless of status",
    "parsed": "Freshly extracted from source, awaiting triage",
    "triaged": "Approved during triage, awaiting review",
    "reviewed": "Quote refined and context added, awaiting caption",
    "ready": "Caption generated, ready for publishing",
    "published": "Published and shared",
    "rejected": "Dismissed during triage (reversible)",
}


class FilterModal(ModalScreen[IdeaStatus | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    FilterModal {
        align: center middle;
    }

    FilterModal > Vertical {
        width: 50;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    FilterModal Label {
        width: 100%;
        margin-bottom: 1;
    }

    FilterModal RadioSet {
        width: 100%;
        margin-bottom: 1;
    }

    FilterModal .hint {
        color: $text-muted;
        width: 100%;
    }

    FilterModal .status-desc {
        color: $text-muted;
        margin: 0 0 0 4;
        width: 100%;
    }
    """

    _OPTIONS = ["All", "parsed", "triaged", "reviewed", "ready", "published", "rejected"]

    def __init__(self, current_filter: IdeaStatus | None = None) -> None:
        super().__init__()
        self._current_filter = current_filter

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]Filter by status[/bold]")
            current_value = self._current_filter.value if self._current_filter else "All"
            radio_set = RadioSet(
                *[RadioButton(opt, value=(opt == current_value)) for opt in self._OPTIONS],
                id="filter-radio",
            )
            yield radio_set
            yield Static("", id="status-desc", classes="status-desc")
            yield Static("Space to select, Enter to apply, Esc to cancel", classes="hint")

    def on_mount(self) -> None:
        self._update_description()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self._update_description()

    def _update_description(self) -> None:
        radio_set = self.query_one("#filter-radio", RadioSet)
        idx = radio_set.pressed_index
        if idx is not None and idx < len(self._OPTIONS):
            desc = _STATUS_DESCRIPTIONS.get(self._OPTIONS[idx], "")
            self.query_one("#status-desc", Static).update(desc)

    def on_key(self, event: Key) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self._apply()

    def _apply(self) -> None:
        radio_set = self.query_one("#filter-radio", RadioSet)
        idx = radio_set.pressed_index
        if idx is None or idx == 0:
            self.dismiss(None)
        else:
            self.dismiss(IdeaStatus(self._OPTIONS[idx]))

    def action_cancel(self) -> None:
        self.dismiss(self._current_filter)
