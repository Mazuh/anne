from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RadioButton, RadioSet

from anne.models import IdeaStatus


class FilterModal(ModalScreen[IdeaStatus | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    FilterModal {
        align: center middle;
    }

    FilterModal > Vertical {
        width: 40;
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

    FilterModal Button {
        margin: 0 1;
    }
    """

    _OPTIONS = ["All", "parsed", "triaged", "reviewed", "ready", "rejected"]

    def __init__(self, current_filter: IdeaStatus | None = None) -> None:
        super().__init__()
        self._current_filter = current_filter

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]Filter by status[/bold]")
            current_value = self._current_filter.value if self._current_filter else "All"
            yield RadioSet(
                *[RadioButton(opt, value=(opt == current_value)) for opt in self._OPTIONS],
                id="filter-radio",
            )
            with Horizontal():
                yield Button("Apply", variant="primary", id="apply-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply-btn":
            radio_set = self.query_one("#filter-radio", RadioSet)
            idx = radio_set.pressed_index
            if idx is None or idx == 0:
                self.dismiss(None)
            else:
                status_value = self._OPTIONS[idx]
                self.dismiss(IdeaStatus(status_value))
        else:
            self.dismiss(self._current_filter)

    def action_cancel(self) -> None:
        self.dismiss(self._current_filter)
