from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Button, Input, Static, TextArea

from anne.config.settings import Settings
from anne.db.connection import get_connection
from anne.models import Book, IdeaStatus
from anne.services.books import get_book
from anne.services.ideas import get_idea, reject_idea
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
