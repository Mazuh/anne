from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Button, Input, Static, TextArea

from anne.config.settings import Settings
from anne.db.connection import get_connection
from anne.models import Book, IdeaStatus
from anne.services.books import get_book
from anne.services.ideas import (
    caption_idea,
    get_idea,
    reject_idea,
    review_idea,
    triage_approve_idea,
)
from anne.tui.screens.workspace import BookWorkspaceScreen
from anne.tui.widgets.idea_list import IdeaList
from tests.test_tui.conftest import wait_for_workers

_CSS_PATH = Path(__file__).parents[2] / "src" / "anne" / "tui" / "app.tcss"


class WorkspaceTestApp(App):
    """Minimal test app that opens directly into a workspace."""

    CSS_PATH = _CSS_PATH

    def __init__(self, settings: Settings, book: Book) -> None:
        super().__init__()
        self.settings = settings
        self._book = book

    def on_mount(self) -> None:
        self.push_screen(BookWorkspaceScreen(self._book))


@pytest.fixture
def workspace_app(seeded_settings: Settings) -> WorkspaceTestApp:
    with get_connection(seeded_settings.db_path) as conn:
        book = get_book(conn, "test-book")
    return WorkspaceTestApp(seeded_settings, book)


class TestWorkspaceLoading:
    async def test_workspace_loads_ideas(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            assert len(idea_list.ideas) == 10

    async def test_workspace_shows_detail_on_select(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            content = workspace_app.screen.query_one("#idea-detail-content", Static)
            text = str(content.content)
            assert "Quote 1" in text

    async def test_navigate_with_j_k(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            await pilot.press("j")
            await pilot.pause()
            assert idea_list.cursor_row == 1


class TestWorkspaceNavigation:
    async def test_next_prev_page(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            assert idea_list.page == 1
            await pilot.press("n")
            await wait_for_workers(workspace_app)
            assert idea_list.page == 1


class TestWorkspaceMutations:
    async def test_triage_idea(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()
            assert idea is not None
            assert idea.status == IdeaStatus.parsed

            await pilot.press("a")
            await wait_for_workers(workspace_app)

            with get_connection(workspace_app.settings.db_path) as conn:
                updated = get_idea(conn, idea.id)
            assert updated.status == IdeaStatus.triaged

    async def test_unreject_idea(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()

            with get_connection(workspace_app.settings.db_path) as conn:
                reject_idea(conn, idea.id, "test reason")

            await pilot.press("r")
            await wait_for_workers(workspace_app)

            await pilot.press("u")
            await wait_for_workers(workspace_app)

            with get_connection(workspace_app.settings.db_path) as conn:
                updated = get_idea(conn, idea.id)
            assert updated.status == IdeaStatus.parsed

    async def test_reject_via_confirm_modal(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()
            assert idea is not None
            assert idea.status == IdeaStatus.parsed

            await pilot.press("x")
            await pilot.pause()

            from anne.tui.modals.confirm import ConfirmModal
            assert isinstance(workspace_app.screen, ConfirmModal)

            # Click confirm button
            confirm_btn = workspace_app.screen.query_one("#confirm-btn", Button)
            await pilot.click(confirm_btn)
            await wait_for_workers(workspace_app)

            with get_connection(workspace_app.settings.db_path) as conn:
                updated = get_idea(conn, idea.id)
            assert updated.status == IdeaStatus.rejected

    async def test_reject_ready_idea_via_confirm_modal(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()
            assert idea is not None

            # Advance to ready
            with get_connection(workspace_app.settings.db_path) as conn:
                triage_approve_idea(conn, idea.id)
                review_idea(conn, idea.id, "refined quote", "some comment")
                from anne.services.ideas import update_idea
                update_idea(conn, idea.id, status="ready")

            await pilot.press("r")
            await wait_for_workers(workspace_app)

            await pilot.press("x")
            await pilot.pause()

            from anne.tui.modals.confirm import ConfirmModal
            assert isinstance(workspace_app.screen, ConfirmModal)

            confirm_btn = workspace_app.screen.query_one("#confirm-btn", Button)
            await pilot.click(confirm_btn)
            await wait_for_workers(workspace_app)

            with get_connection(workspace_app.settings.db_path) as conn:
                updated = get_idea(conn, idea.id)
            assert updated.status == IdeaStatus.rejected

    async def test_publish_ignored_for_non_ready_idea(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()
            assert idea is not None
            assert idea.status == IdeaStatus.parsed

            await pilot.press("P")
            await pilot.pause()

            # No modal should open — still on the workspace screen
            from anne.tui.modals.confirm import ConfirmModal
            assert not isinstance(workspace_app.screen, ConfirmModal)

            with get_connection(workspace_app.settings.db_path) as conn:
                updated = get_idea(conn, idea.id)
            assert updated.status == IdeaStatus.parsed

    async def test_publish_via_confirm_modal(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()
            assert idea is not None

            # Advance idea to ready: parsed → triaged → reviewed → ready
            with get_connection(workspace_app.settings.db_path) as conn:
                triage_approve_idea(conn, idea.id)
                review_idea(conn, idea.id, "Refined quote", "Context")
                caption_idea(conn, idea.id, "Caption text", "[]")

            await pilot.press("r")
            await wait_for_workers(workspace_app)

            await pilot.press("P")
            await pilot.pause()

            from anne.tui.modals.confirm import ConfirmModal
            assert isinstance(workspace_app.screen, ConfirmModal)

            confirm_btn = workspace_app.screen.query_one("#confirm-btn", Button)
            await pilot.click(confirm_btn)
            await wait_for_workers(workspace_app)

            with get_connection(workspace_app.settings.db_path) as conn:
                updated = get_idea(conn, idea.id)
            assert updated.status == IdeaStatus.published
            assert updated.published_at is not None


class TestWorkspaceFilter:
    async def test_filter_modal_opens(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            await pilot.press("f")
            await pilot.pause()
            from anne.tui.modals.filter import FilterModal
            assert isinstance(workspace_app.screen, FilterModal)

    async def test_search_input_shows(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            search = workspace_app.screen.query_one("#search-input", Input)
            assert search.display is False
            await pilot.press("slash")
            await pilot.pause()
            assert search.display is True

    async def test_search_filters_results(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            assert len(idea_list.ideas) == 10

            # Open search, type a query that matches only "Quote 5", submit
            await pilot.press("slash")
            await pilot.pause()
            search = workspace_app.screen.query_one("#search-input", Input)
            search.value = "Quote 5"
            await pilot.press("enter")
            await wait_for_workers(workspace_app)

            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            assert len(idea_list.ideas) == 1
            assert "Quote 5" in (idea_list.ideas[0].raw_quote or "")


class TestWorkspaceEdit:
    async def test_edit_field_modal_opens(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            await pilot.press("e")
            await pilot.pause()
            from anne.tui.modals.edit_field import EditFieldModal
            assert isinstance(workspace_app.screen, EditFieldModal)

    async def test_edit_tags_modal_opens(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            await pilot.press("t")
            await pilot.pause()
            from anne.tui.modals.edit_field import EditFieldModal
            assert isinstance(workspace_app.screen, EditFieldModal)

    async def test_edit_saves_to_db(self, workspace_app: WorkspaceTestApp) -> None:
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()
            assert idea is not None

            await pilot.press("e")
            await pilot.pause()

            from anne.tui.modals.edit_field import EditFieldModal
            assert isinstance(workspace_app.screen, EditFieldModal)

            text_area = workspace_app.screen.query_one("#value-input", TextArea)
            text_area.clear()
            text_area.insert("Updated quote text")

            save_btn = workspace_app.screen.query_one("#save-btn", Button)
            await pilot.click(save_btn)
            await wait_for_workers(workspace_app)

            with get_connection(workspace_app.settings.db_path) as conn:
                updated = get_idea(conn, idea.id)
            assert updated.raw_quote == "Updated quote text"


@pytest.fixture
def tagged_workspace_app(tui_settings: Settings) -> WorkspaceTestApp:
    """Workspace with ideas that have tags."""
    from anne.db.migrate import apply_schema
    from anne.models import SourceType
    from anne.services.books import create_book
    from anne.services.ideas import insert_ideas
    from anne.services.parsers import ParsedIdea
    from anne.services.sources import import_source

    apply_schema(tui_settings.db_path)

    with get_connection(tui_settings.db_path) as conn:
        book = create_book(conn, "Tagged Book", "Author")
        source = import_source(
            conn, book.id, SourceType.kindle_export_html, "s/notes.html", "fp1",
        )
        # Create 3 ideas, advance 2 to ready with tags
        for quote, tags in [("Q1", '["philosophy", "ethics"]'), ("Q2", '["philosophy", "power"]')]:
            ideas = insert_ideas(conn, book.id, source.id, [ParsedIdea(raw_quote=quote)])
            triage_approve_idea(conn, ideas[0].id)
            review_idea(conn, ideas[0].id, quote, "ctx")
            caption_idea(conn, ideas[0].id, "caption", tags)
        # One parsed idea without tags
        insert_ideas(conn, book.id, source.id, [ParsedIdea(raw_quote="Q3")])

    with get_connection(tui_settings.db_path) as conn:
        book_obj = get_book(conn, "tagged-book")
    return WorkspaceTestApp(tui_settings, book_obj)


class TestWorkspaceActionMenu:
    async def test_action_menu_opens_for_parsed(self, workspace_app: WorkspaceTestApp) -> None:
        """Pressing A on a parsed idea shows the action modal with 'Triage with LLM'."""
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()
            assert idea is not None
            assert idea.status == IdeaStatus.parsed

            await pilot.press("A")
            await pilot.pause()
            from anne.tui.modals.action_menu import ActionModal
            assert isinstance(workspace_app.screen, ActionModal)

            from textual.widgets import RadioButton
            buttons = workspace_app.screen.query(RadioButton)
            labels = [str(b.label) for b in buttons]
            assert "Triage with LLM" in labels

    async def test_action_menu_shows_review_for_triaged(self, workspace_app: WorkspaceTestApp) -> None:
        """Pressing A on a triaged idea shows 'Review with LLM'."""
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()
            assert idea is not None

            # Triage the idea first
            with get_connection(workspace_app.settings.db_path) as conn:
                triage_approve_idea(conn, idea.id)

            await pilot.press("r")
            await wait_for_workers(workspace_app)

            await pilot.press("A")
            await pilot.pause()
            from anne.tui.modals.action_menu import ActionModal
            assert isinstance(workspace_app.screen, ActionModal)

            from textual.widgets import RadioButton
            buttons = workspace_app.screen.query(RadioButton)
            labels = [str(b.label) for b in buttons]
            assert "Review with LLM" in labels

    async def test_action_menu_shows_caption_for_reviewed(self, workspace_app: WorkspaceTestApp) -> None:
        """Pressing A on a reviewed idea shows 'Caption with LLM'."""
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()
            assert idea is not None

            with get_connection(workspace_app.settings.db_path) as conn:
                triage_approve_idea(conn, idea.id)
                review_idea(conn, idea.id, "Refined quote", "Context")

            await pilot.press("r")
            await wait_for_workers(workspace_app)

            await pilot.press("A")
            await pilot.pause()
            from anne.tui.modals.action_menu import ActionModal
            assert isinstance(workspace_app.screen, ActionModal)

            from textual.widgets import RadioButton
            buttons = workspace_app.screen.query(RadioButton)
            labels = [str(b.label) for b in buttons]
            assert "Caption with LLM" in labels

    async def test_action_menu_notifies_no_actions_for_rejected(self, workspace_app: WorkspaceTestApp) -> None:
        """Pressing A on a rejected idea shows a warning notification, no modal."""
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()
            assert idea is not None

            with get_connection(workspace_app.settings.db_path) as conn:
                reject_idea(conn, idea.id, "test")

            await pilot.press("r")
            await wait_for_workers(workspace_app)

            await pilot.press("A")
            await pilot.pause()
            # Should NOT open a modal — should stay on workspace
            from anne.tui.screens.workspace import BookWorkspaceScreen
            assert isinstance(workspace_app.screen, BookWorkspaceScreen)


class TestTagFilter:
    async def test_tag_filter_modal_opens(self, tagged_workspace_app: WorkspaceTestApp) -> None:
        async with tagged_workspace_app.run_test() as pilot:
            await wait_for_workers(tagged_workspace_app)
            await pilot.press("T")
            await wait_for_workers(tagged_workspace_app)
            await pilot.pause()
            from anne.tui.modals.tag_filter import TagFilterModal
            assert isinstance(tagged_workspace_app.screen, TagFilterModal)

    async def test_tag_filter_filters_list(self, tagged_workspace_app: WorkspaceTestApp) -> None:
        async with tagged_workspace_app.run_test() as pilot:
            await wait_for_workers(tagged_workspace_app)
            idea_list = tagged_workspace_app.screen.query_one("#idea-list", IdeaList)
            assert len(idea_list.ideas) == 3  # all ideas

            # Open tag filter modal
            await pilot.press("T")
            await wait_for_workers(tagged_workspace_app)
            await pilot.pause()

            from anne.tui.modals.tag_filter import TagFilterModal
            assert isinstance(tagged_workspace_app.screen, TagFilterModal)

            from textual.widgets import RadioButton
            # Options: All, ethics, philosophy, power — select "ethics" (index 1)
            buttons = tagged_workspace_app.screen.query(RadioButton)
            await pilot.click(buttons[1])  # "ethics"
            await pilot.pause()
            await pilot.press("enter")  # apply
            await wait_for_workers(tagged_workspace_app)

            idea_list = tagged_workspace_app.screen.query_one("#idea-list", IdeaList)
            assert len(idea_list.ideas) == 1
            assert idea_list.ideas[0].raw_quote == "Q1"

    async def test_tags_visible_in_detail(self, tagged_workspace_app: WorkspaceTestApp) -> None:
        async with tagged_workspace_app.run_test() as pilot:
            await wait_for_workers(tagged_workspace_app)
            content = tagged_workspace_app.screen.query_one("#idea-detail-content", Static)
            text = str(content.content)
            assert "Tags:" in text
            assert "philosophy" in text


class TestAIPrompt:
    async def test_ai_prompt_ignored_for_parsed_idea(self, workspace_app: WorkspaceTestApp) -> None:
        """Pressing ? on a parsed idea should not open any modal."""
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()
            assert idea is not None
            assert idea.status == IdeaStatus.parsed

            await pilot.press("question_mark")
            await pilot.pause()

            from anne.tui.modals.custom_prompt import CustomPromptModal
            assert not isinstance(workspace_app.screen, CustomPromptModal)

    async def test_ai_prompt_opens_modal_for_ready_idea(self, workspace_app: WorkspaceTestApp) -> None:
        """Pressing ? on a ready idea should open the CustomPromptModal."""
        async with workspace_app.run_test() as pilot:
            await wait_for_workers(workspace_app)
            idea_list = workspace_app.screen.query_one("#idea-list", IdeaList)
            idea = idea_list.get_selected_idea()
            assert idea is not None

            with get_connection(workspace_app.settings.db_path) as conn:
                triage_approve_idea(conn, idea.id)
                review_idea(conn, idea.id, "Refined quote", "Context")
                caption_idea(conn, idea.id, "Caption text", "[]")

            await pilot.press("r")
            await wait_for_workers(workspace_app)

            await pilot.press("question_mark")
            await pilot.pause()

            from anne.tui.modals.custom_prompt import CustomPromptModal
            assert isinstance(workspace_app.screen, CustomPromptModal)
