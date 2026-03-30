import pytest
from textual.widgets import DataTable

from anne.config.settings import Settings
from anne.tui import AnneApp
from tests.test_tui.conftest import wait_for_workers


@pytest.fixture
def app(seeded_settings: Settings) -> AnneApp:
    return AnneApp(seeded_settings)


@pytest.fixture
def empty_app(empty_settings: Settings) -> AnneApp:
    return AnneApp(empty_settings)


class TestDashboardActionMenu:
    async def test_action_menu_opens(self, app: AnneApp) -> None:
        async with app.run_test() as pilot:
            await wait_for_workers(app)
            await pilot.press("A")
            await pilot.pause()
            from anne.tui.modals.action_menu import ActionModal
            assert isinstance(app.screen, ActionModal)

    async def test_action_menu_escape_cancels(self, app: AnneApp) -> None:
        async with app.run_test() as pilot:
            await wait_for_workers(app)
            await pilot.press("A")
            await pilot.pause()
            from anne.tui.modals.action_menu import ActionModal
            assert isinstance(app.screen, ActionModal)
            await pilot.press("escape")
            await pilot.pause()
            from anne.tui.screens.dashboard import DashboardScreen
            assert isinstance(app.screen, DashboardScreen)


class TestDashboard:
    async def test_dashboard_loads_with_books(self, app: AnneApp) -> None:
        async with app.run_test() as pilot:
            await wait_for_workers(app)
            table = app.screen.query_one("#dashboard-table", DataTable)
            assert table.row_count == 1

    async def test_dashboard_shows_book_title(self, app: AnneApp) -> None:
        async with app.run_test() as pilot:
            await wait_for_workers(app)
            table = app.screen.query_one("#dashboard-table", DataTable)
            first_row_key = list(table.rows.keys())[0]
            row_data = table.get_row(first_row_key)
            assert row_data[0] == "Test Book"
            assert row_data[1] == "Test Author"

    async def test_dashboard_shows_idea_counts(self, app: AnneApp) -> None:
        async with app.run_test() as pilot:
            await wait_for_workers(app)
            table = app.screen.query_one("#dashboard-table", DataTable)
            first_row_key = list(table.rows.keys())[0]
            row_data = table.get_row(first_row_key)
            # Columns: Book, Author, Parsed, Triaged, Reviewed, Ready, Queued, Published, Rejected, Total
            assert row_data[2] == "10"  # Parsed
            assert row_data[9] == "10"  # Total

    async def test_dashboard_empty(self, empty_app: AnneApp) -> None:
        async with empty_app.run_test() as pilot:
            await wait_for_workers(empty_app)
            table = empty_app.screen.query_one("#dashboard-table", DataTable)
            assert table.row_count == 0

    async def test_dashboard_quit(self, app: AnneApp) -> None:
        async with app.run_test() as pilot:
            await pilot.press("q")

    async def test_dashboard_refresh(self, app: AnneApp) -> None:
        async with app.run_test() as pilot:
            await wait_for_workers(app)
            table = app.screen.query_one("#dashboard-table", DataTable)
            initial_count = table.row_count
            await pilot.press("r")
            await wait_for_workers(app)
            assert table.row_count == initial_count

    async def test_dashboard_open_book(self, app: AnneApp) -> None:
        async with app.run_test() as pilot:
            await wait_for_workers(app)
            await pilot.press("enter")
            await wait_for_workers(app)
            from anne.tui.screens.workspace import BookWorkspaceScreen
            assert isinstance(app.screen, BookWorkspaceScreen)
