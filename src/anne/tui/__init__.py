from pathlib import Path

from textual.app import App

from anne.config.settings import Settings
from anne.tui.screens.dashboard import DashboardScreen

_CSS_PATH = Path(__file__).parent / "app.tcss"


class AnneApp(App):
    CSS_PATH = _CSS_PATH
    TITLE = "Anne"

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen())
