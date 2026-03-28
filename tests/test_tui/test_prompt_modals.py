from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Button

from anne.tui.modals.custom_prompt import CustomPromptModal
from anne.tui.modals.prompt_response import PromptResponseModal

_CSS_PATH = Path(__file__).parents[2] / "src" / "anne" / "tui" / "app.tcss"


class PromptInputTestApp(App):
    CSS_PATH = _CSS_PATH

    def __init__(self) -> None:
        super().__init__()
        self.result: str | None = "NOT_SET"

    def on_mount(self) -> None:
        self.push_screen(
            CustomPromptModal(),
            callback=self._on_result,
        )

    def _on_result(self, result: str | None) -> None:
        self.result = result
        self.exit()


class ResponseTestApp(App):
    CSS_PATH = _CSS_PATH

    def __init__(self, response: str) -> None:
        super().__init__()
        self._response = response
        self.dismissed = False

    def on_mount(self) -> None:
        self.push_screen(
            PromptResponseModal(self._response),
            callback=self._on_result,
        )

    def _on_result(self, result: None) -> None:
        self.dismissed = True
        self.exit()


class TestCustomPromptModal:
    async def test_submit_with_text(self) -> None:
        app = PromptInputTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            from textual.widgets import TextArea

            text_area = app.screen.query_one("#prompt-input", TextArea)
            text_area.clear()
            text_area.insert("Reword this casually")
            btn = app.screen.query_one("#submit-btn", Button)
            await pilot.click(btn)
            await pilot.pause()
        assert app.result == "Reword this casually"

    async def test_submit_empty_shows_warning(self) -> None:
        app = PromptInputTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            btn = app.screen.query_one("#submit-btn", Button)
            await pilot.click(btn)
            await pilot.pause()
            # Should still be on the modal (not dismissed)
            assert app.result == "NOT_SET"

    async def test_cancel_returns_none(self) -> None:
        app = PromptInputTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            btn = app.screen.query_one("#cancel-btn", Button)
            await pilot.click(btn)
            await pilot.pause()
        assert app.result is None

    async def test_escape_returns_none(self) -> None:
        app = PromptInputTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert app.result is None


class TestPromptResponseModal:
    async def test_displays_response(self) -> None:
        app = ResponseTestApp("Here is the LLM response text.")
        async with app.run_test() as pilot:
            await pilot.pause()
            from textual.widgets import Static

            static = app.screen.query_one("#response-text", Static)
            assert "LLM response text" in str(static.render())

    async def test_close_button_dismisses(self) -> None:
        app = ResponseTestApp("Some response")
        async with app.run_test() as pilot:
            await pilot.pause()
            btn = app.screen.query_one("#close-btn", Button)
            await pilot.click(btn)
            await pilot.pause()
        assert app.dismissed is True

    async def test_escape_dismisses(self) -> None:
        app = ResponseTestApp("Some response")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert app.dismissed is True
