from pathlib import Path
from unittest.mock import patch

import pytest
from textual.app import App
from textual.widgets import Button, Static

from anne.tui.modals.confirm import ConfirmModal
from anne.tui.modals.custom_prompt import CustomPromptModal
from anne.tui.modals.loading import LoadingModal
from anne.tui.modals.prompt_response import PromptResponseModal

_CSS_PATH = Path(__file__).parents[2] / "src" / "anne" / "tui" / "app.tcss"


class ConfirmTestApp(App):
    CSS_PATH = _CSS_PATH

    def __init__(self, show_reason: bool = False) -> None:
        super().__init__()
        self._show_reason = show_reason
        self.result: tuple[bool, str] | None = None

    def on_mount(self) -> None:
        self.push_screen(
            ConfirmModal("Are you sure?", show_reason=self._show_reason),
            callback=self._on_result,
        )

    def _on_result(self, result: tuple[bool, str]) -> None:
        self.result = result
        self.exit()


class PromptInputTestApp(App):
    CSS_PATH = _CSS_PATH

    def __init__(self) -> None:
        super().__init__()
        self._result_sentinel = True
        self.result: str | None = None

    def on_mount(self) -> None:
        self.push_screen(
            CustomPromptModal(),
            callback=self._on_result,
        )

    def _on_result(self, result: str | None) -> None:
        self._result_sentinel = False
        self.result = result
        self.exit()


class ResponseTestApp(App):
    CSS_PATH = _CSS_PATH

    def __init__(self, response: str, prompt: str = "") -> None:
        super().__init__()
        self._response = response
        self._prompt = prompt
        self.dismissed = False
        self._result_sentinel = True
        self.result: bool | None = None

    def on_mount(self) -> None:
        self.push_screen(
            PromptResponseModal(self._response, prompt=self._prompt),
            callback=self._on_result,
        )

    def _on_result(self, result: bool | None) -> None:
        self.dismissed = True
        self._result_sentinel = False
        self.result = result
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
            from textual.widgets import TextArea

            text_area = app.screen.query_one("#prompt-input", TextArea)
            text_area.clear()
            text_area.insert("Reword this casually")
            btn = app.screen.query_one("#submit-btn", Button)
            await pilot.click(btn)
            await pilot.pause()
        assert app.result == "Reword this casually"

    async def test_ctrl_s_submits(self) -> None:
        app = PromptInputTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            from textual.widgets import TextArea

            text_area = app.screen.query_one("#prompt-input", TextArea)
            text_area.clear()
            text_area.insert("Translate to English")
            await pilot.press("ctrl+s")
            await pilot.pause()
        assert app.result == "Translate to English"

    async def test_ctrl_s_on_empty_does_not_submit(self) -> None:
        app = PromptInputTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert app._result_sentinel is True

    async def test_submit_empty_shows_warning(self) -> None:
        app = PromptInputTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            btn = app.screen.query_one("#submit-btn", Button)
            await pilot.click(btn)
            await pilot.pause()
            # Should still be on the modal (not dismissed)
            assert app._result_sentinel is True

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
            assert "Ctrl+S to submit" in text
            assert "Esc to cancel." in text

    async def test_initial_prompt_prefills_input(self) -> None:
        class PrefillApp(App):
            CSS_PATH = _CSS_PATH

            def __init__(self) -> None:
                super().__init__()
                self._result_sentinel = True
                self.result: str | None = None

            def on_mount(self) -> None:
                self.push_screen(
                    CustomPromptModal(initial_prompt="old text"),
                    callback=self._on_result,
                )

            def _on_result(self, result: str | None) -> None:
                self._result_sentinel = False
                self.result = result
                self.exit()

        app = PrefillApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            from textual.widgets import TextArea

            text_area = app.screen.query_one("#prompt-input", TextArea)
            assert text_area.text == "old text"


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
            assert "r to retry" in text
            assert "Esc to close" in text

    async def test_displays_prompt(self) -> None:
        app = ResponseTestApp("The response", prompt="What does this mean?")
        async with app.run_test() as pilot:
            await pilot.pause()
            prompt_label = app.screen.query_one("#prompt-label", Static)
            assert "What does this mean?" in str(prompt_label.render())

    async def test_no_prompt_label_when_empty(self) -> None:
        app = ResponseTestApp("The response")
        async with app.run_test() as pilot:
            await pilot.pause()
            results = app.screen.query("#prompt-label")
            assert len(results) == 0

    async def test_retry_button_dismisses_with_true(self) -> None:
        app = ResponseTestApp("Some response", prompt="my prompt")
        async with app.run_test() as pilot:
            await pilot.pause()
            btn = app.screen.query_one("#retry-btn", Button)
            await pilot.click(btn)
            await pilot.pause()
        assert app.dismissed is True
        assert app.result is True

    async def test_r_key_triggers_retry(self) -> None:
        app = ResponseTestApp("Some response", prompt="my prompt")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()
        assert app.dismissed is True
        assert app.result is True

    async def test_close_returns_none(self) -> None:
        app = ResponseTestApp("Some response")
        async with app.run_test() as pilot:
            await pilot.pause()
            btn = app.screen.query_one("#close-btn", Button)
            await pilot.click(btn)
            await pilot.pause()
        assert app.result is None


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


class TestConfirmModal:
    async def test_ctrl_s_confirms_with_reason(self) -> None:
        app = ConfirmTestApp(show_reason=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            from textual.widgets import TextArea

            text_area = app.screen.query_one("#reason-input", TextArea)
            text_area.insert("not relevant")
            await pilot.press("ctrl+s")
            await pilot.pause()
        assert app.result == (True, "not relevant")

    async def test_ctrl_s_confirms_without_reason(self) -> None:
        app = ConfirmTestApp(show_reason=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+s")
            await pilot.pause()
        assert app.result == (True, "")

    async def test_escape_cancels(self) -> None:
        app = ConfirmTestApp(show_reason=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert app.result == (False, "")
