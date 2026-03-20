from pathlib import Path

import pytest
from textual.app import App

from anne.tui.modals.action_menu import ActionModal

_CSS_PATH = Path(__file__).parents[2] / "src" / "anne" / "tui" / "app.tcss"


class ModalTestApp(App):
    CSS_PATH = _CSS_PATH

    def __init__(self, options: list[str], descriptions: dict[str, str] | None = None) -> None:
        super().__init__()
        self._options = options
        self._descriptions = descriptions
        self.result: str | None = "NOT_SET"

    def on_mount(self) -> None:
        self.push_screen(
            ActionModal("Test Actions", self._options, self._descriptions),
            callback=self._on_result,
        )

    def _on_result(self, result: str | None) -> None:
        self.result = result
        self.exit()


class TestActionModal:
    async def test_modal_renders_options(self) -> None:
        app = ModalTestApp(["Option A", "Option B"])
        async with app.run_test() as pilot:
            await pilot.pause()
            from textual.widgets import RadioButton
            buttons = app.screen.query(RadioButton)
            labels = [str(b.label) for b in buttons]
            assert "Option A" in labels
            assert "Option B" in labels

    async def test_enter_dismisses_with_selection(self) -> None:
        app = ModalTestApp(["Alpha", "Beta"])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
        assert app.result == "Alpha"

    async def test_escape_dismisses_with_none(self) -> None:
        app = ModalTestApp(["Alpha", "Beta"])
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert app.result is None

    async def test_description_shown(self) -> None:
        app = ModalTestApp(
            ["Do X", "Do Y"],
            descriptions={"Do X": "Description for X", "Do Y": "Description for Y"},
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            from textual.widgets import Static
            desc = app.screen.query_one("#action-desc", Static)
            text = str(desc.content)
            assert "Description for X" in text
