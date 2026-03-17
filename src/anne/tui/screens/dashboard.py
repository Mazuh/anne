from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header

from anne.models import Book, IdeaStatus


class DashboardScreen(Screen):
    TITLE = "Anne"
    SUB_TITLE = "Dashboard"

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
        Binding("enter", "open_book", "Open book"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._books: list[Book] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="dashboard-table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        table.add_columns("Book", "Author", "Parsed", "Triaged", "Reviewed", "Ready", "Rejected", "Total")
        self._load_data()

    @work(thread=True)
    def _load_data(self) -> None:
        from anne.db.connection import get_connection
        from anne.services.books import get_book_stats, list_books

        settings = self.app.settings
        with get_connection(settings.db_path) as conn:
            books = list_books(conn)
            rows: list[tuple[Book, dict]] = []
            for book in books:
                stats = get_book_stats(conn, book.id)
                rows.append((book, stats))

        self.app.call_from_thread(self._populate_table, rows)

    def _populate_table(self, rows: list[tuple[Book, dict]]) -> None:
        from textual.css.query import NoMatches

        try:
            table = self.query_one("#dashboard-table", DataTable)
        except NoMatches:
            return  # Screen was dismissed before worker completed
        table.clear()
        self._books = []
        for book, stats in rows:
            self._books.append(book)
            idea_counts = stats["ideas"]
            table.add_row(
                book.title,
                book.author,
                str(idea_counts.get(IdeaStatus.parsed, 0)),
                str(idea_counts.get(IdeaStatus.triaged, 0)),
                str(idea_counts.get(IdeaStatus.reviewed, 0)),
                str(idea_counts.get(IdeaStatus.ready, 0)),
                str(idea_counts.get(IdeaStatus.rejected, 0)),
                str(stats["ideas_total"]),
                key=str(book.id),
            )

    def action_refresh(self) -> None:
        self._load_data()

    def action_quit(self) -> None:
        self.app.exit()

    def action_open_book(self) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        if table.row_count == 0:
            return
        cursor_row = table.cursor_row
        if cursor_row < 0 or cursor_row >= len(self._books):
            return
        book = self._books[cursor_row]
        from anne.tui.screens.workspace import BookWorkspaceScreen
        self.app.push_screen(BookWorkspaceScreen(book))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_open_book()
