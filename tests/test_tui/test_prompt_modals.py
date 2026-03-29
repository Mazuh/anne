from pathlib import Path
from unittest.mock import patch

import pytest
from textual.app import App
from textual.widgets import Button, Static

from anne.tui.modals.custom_prompt import CustomPromptModal
from anne.tui.modals.loading import LoadingModal
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


class LoadingTestApp(App):
    CSS_PATH = _CSS_PATH

    def __init__(self) -> None:
        super().__init__()
        self.dismissed = False
        self.cancelled: bool | None = None

    def on_mount(self) -> None:
        self.push_screen(
            LoadingModal(),
            callback=self._on_result,
        )

    def _on_result(self, result: bool) -> None:
        self.dismissed = True
        self.cancelled = result
        self.exit()


class TestCustomPromptModal:
    async def test_submit_with_text(self) -> None:
        app = PromptInputTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            from textual.widgets import Input

            input_widget = app.screen.query_one("#prompt-input", Input)
            input_widget.value = "Reword this casually"
            btn = app.screen.query_one("#submit-btn", Button)
            await pilot.click(btn)
            await pilot.pause()
        assert app.result == "Reword this casually"

    async def test_enter_submits(self) -> None:
        app = PromptInputTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            from textual.widgets import Input

            input_widget = app.screen.query_one("#prompt-input", Input)
            input_widget.value = "Translate to English"
            await pilot.press("enter")
            await pilot.pause()
        assert app.result == "Translate to English"

    async def test_enter_on_empty_does_not_submit(self) -> None:
        app = PromptInputTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.result == "NOT_SET"

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

    async def test_subtitle_is_read_only(self) -> None:
        app = PromptInputTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            labels = app.screen.query("Label")
            texts = [str(label.render()) for label in labels]
            assert any("read-only" in t for t in texts)

    async def test_hint_label_present(self) -> None:
        app = PromptInputTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            hints = app.screen.query(".hint")
            assert len(hints) == 1
            text = str(hints[0].render())
            assert "Enter to submit" in text
            assert "Esc to cancel" in text


class TestPromptResponseModal:
    async def test_displays_response(self) -> None:
        app = ResponseTestApp("Here is the LLM response text.")
        async with app.run_test() as pilot:
            await pilot.pause()
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

    async def test_c_key_copies(self) -> None:
        app = ResponseTestApp("Copy me")
        async with app.run_test() as pilot:
            await pilot.pause()
            with patch("anne.tui.modals.prompt_response.subprocess.run") as mock_run:
                await pilot.press("c")
                await pilot.pause()
                if __import__("sys").platform == "darwin":
                    mock_run.assert_called_once()

    async def test_hint_label_present(self) -> None:
        app = ResponseTestApp("Some response")
        async with app.run_test() as pilot:
            await pilot.pause()
            hints = app.screen.query(".hint")
            assert len(hints) == 1
            text = str(hints[0].render())
            assert "Esc to close" in text


class TestLoadingModal:
    async def test_renders_label(self) -> None:
        app = LoadingTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            labels = app.screen.query("Label")
            texts = [str(label.render()) for label in labels]
            assert any("Calling LLM" in t for t in texts)

    async def test_escape_dismisses(self) -> None:
        app = LoadingTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert app.dismissed is True

    async def test_escape_returns_completed_false(self) -> None:
        app = LoadingTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert app.cancelled is False

    async def test_renders_cancel_hint(self) -> None:
        app = LoadingTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            hints = app.screen.query(".hint")
            assert len(hints) == 1
            assert "Esc to cancel" in str(hints[0].render())
