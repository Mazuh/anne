from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Label, RadioButton, RadioSet, Static


class ActionModal(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    ActionModal {
        align: center middle;
    }

    ActionModal > Vertical {
        width: 55;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    ActionModal Label {
        width: 100%;
        margin-bottom: 1;
    }

    ActionModal RadioSet {
        width: 100%;
        margin-bottom: 1;
    }

    ActionModal .hint {
        color: $text-muted;
        width: 100%;
    }

    ActionModal .action-desc {
        color: $text-muted;
        margin: 0 0 0 4;
        width: 100%;
    }
    """

    def __init__(
        self,
        title: str,
        options: list[str],
        descriptions: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self._title = title
        self._options = options
        self._descriptions = descriptions or {}

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[bold]{self._title}[/bold]")
            radio_set = RadioSet(
                *[RadioButton(opt, value=(i == 0)) for i, opt in enumerate(self._options)],
                id="action-radio",
            )
            yield radio_set
            yield Static("", id="action-desc", classes="action-desc")
            yield Static("Space to select, Enter to apply, Esc to cancel", classes="hint")

    def on_mount(self) -> None:
        self._update_description()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self._update_description()

    def _update_description(self) -> None:
        radio_set = self.query_one("#action-radio", RadioSet)
        idx = radio_set.pressed_index
        if idx is not None and idx < len(self._options):
            desc = self._descriptions.get(self._options[idx], "")
            self.query_one("#action-desc", Static).update(desc)

    def on_key(self, event: Key) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self._apply()

    def _apply(self) -> None:
        radio_set = self.query_one("#action-radio", RadioSet)
        idx = radio_set.pressed_index
        if idx is not None and idx < len(self._options):
            self.dismiss(self._options[idx])
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
