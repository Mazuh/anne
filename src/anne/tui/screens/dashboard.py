from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header

from anne.models import Book, IdeaStatus
from anne.utils.icloud import ensure_available


_DASHBOARD_ACTIONS = ["Parse Sources", "Triage with LLM", "Review with LLM", "Caption with LLM"]
_DASHBOARD_ACTION_DESCRIPTIONS = {
    "Parse Sources": "Extract ideas from all unparsed source files",
    "Triage with LLM": "Triage all parsed ideas (approve or reject)",
    "Review with LLM": "Refine quotes and add context for triaged ideas",
    "Caption with LLM": "Generate Instagram captions for reviewed ideas",
}


class DashboardScreen(Screen):
    TITLE = "Anne"
    SUB_TITLE = "Dashboard"

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("A", "action_menu", "Actions"),
        Binding("question_mark", "about", "About"),
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
        table.add_columns("Book", "Author", "Parsed", "Triaged", "Reviewed", "Ready", "Queued", "Published", "Rejected", "Total")
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
                str(idea_counts.get(IdeaStatus.queued, 0)),
                str(idea_counts.get(IdeaStatus.published, 0)),
                str(idea_counts.get(IdeaStatus.rejected, 0)),
                str(stats["ideas_total"]),
                key=str(book.id),
            )

    def action_refresh(self) -> None:
        self._load_data()

    def action_about(self) -> None:
        from anne.tui.modals.about import AboutModal
        self.app.push_screen(AboutModal())

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

    # Action menu
    def action_action_menu(self) -> None:
        from anne.tui.modals.action_menu import ActionModal
        self.app.push_screen(
            ActionModal("Pipeline Actions", _DASHBOARD_ACTIONS, _DASHBOARD_ACTION_DESCRIPTIONS),
            callback=self._on_action_selected,
        )

    def _on_action_selected(self, action: str | None) -> None:
        if action == "Parse Sources":
            self._run_parse()
        elif action == "Triage with LLM":
            self._run_triage()
        elif action == "Review with LLM":
            self._run_review()
        elif action == "Caption with LLM":
            self._run_caption()

    @work(thread=True)
    def _run_parse(self) -> None:
        from anne.db.connection import get_connection
        from anne.services.books import list_books
        from anne.services.ideas import get_unparsed_sources, insert_ideas
        from anne.services.parsers import LLM_TYPES, parse_source
        from anne.services.pipeline import format_llm_error

        settings = self.app.settings
        api_key = settings.gemini_api_key

        try:
            total = 0
            with get_connection(settings.db_path) as conn:
                books = list_books(conn)

            for book in books:
                with get_connection(settings.db_path) as conn:
                    sources = get_unparsed_sources(conn, book.id)
                    if not sources:
                        continue

                    from anne.models import SourceType
                    needs_llm = any(SourceType(s.type) in LLM_TYPES for s in sources)
                    if needs_llm and not api_key:
                        self.app.call_from_thread(
                            self.notify, "Gemini API key not configured", severity="error",
                        )
                        return

                    for source in sources:
                        source_path = settings.books_dir / book.slug / source.path
                        try:
                            ensure_available(source_path)
                        except FileNotFoundError:
                            continue
                        content = source_path.read_text(encoding="utf-8")
                        ideas = parse_source(source, content, api_key, settings.max_llm_input_tokens)
                        if ideas:
                            insert_ideas(conn, book.id, source.id, ideas)
                            conn.commit()
                            total += len(ideas)

            label = "idea" if total == 1 else "ideas"
            self.app.call_from_thread(self.notify, f"Parsed {total} {label}.")
            self._load_data()
        except Exception as e:
            self.app.call_from_thread(self.notify, format_llm_error(e), severity="error")

    @work(thread=True)
    def _run_triage(self) -> None:
        from anne.db.connection import get_connection
        from anne.services.books import list_books
        from anne.services.ideas import get_ideas_by_status
        from anne.services.pipeline import format_llm_error, triage_book_ideas

        settings = self.app.settings
        api_key = settings.gemini_api_key
        if not api_key:
            self.app.call_from_thread(self.notify, "Gemini API key not configured", severity="error")
            return

        try:
            total = 0
            with get_connection(settings.db_path) as conn:
                books = list_books(conn)

            for book in books:
                with get_connection(settings.db_path) as conn:
                    parsed_ideas = get_ideas_by_status(conn, book.id, IdeaStatus.parsed)
                    if not parsed_ideas:
                        continue
                    total += triage_book_ideas(
                        conn,
                        api_key=api_key,
                        book_title=book.title,
                        book_author=book.author,
                        ideas=parsed_ideas,
                        chunk_size=settings.triage_chunk_size,
                        max_input_tokens=settings.max_llm_input_tokens,
                        llm_call_interval=settings.llm_call_interval,
                    )

            label = "idea" if total == 1 else "ideas"
            self.app.call_from_thread(self.notify, f"Triaged {total} {label}.")
            self._load_data()
        except Exception as e:
            self.app.call_from_thread(self.notify, format_llm_error(e), severity="error")

    @work(thread=True)
    def _run_review(self) -> None:
        from anne.db.connection import get_connection
        from anne.services.books import list_books
        from anne.services.ideas import get_ideas_by_status
        from anne.services.pipeline import format_llm_error, review_book_ideas

        settings = self.app.settings
        api_key = settings.gemini_api_key
        if not api_key:
            self.app.call_from_thread(self.notify, "Gemini API key not configured", severity="error")
            return

        try:
            total = 0
            with get_connection(settings.db_path) as conn:
                books = list_books(conn)

            for book in books:
                with get_connection(settings.db_path) as conn:
                    triaged_ideas = get_ideas_by_status(conn, book.id, IdeaStatus.triaged)
                    if not triaged_ideas:
                        continue
                    total += review_book_ideas(
                        conn,
                        api_key=api_key,
                        book_title=book.title,
                        book_author=book.author,
                        ideas=triaged_ideas,
                        chunk_size=settings.review_chunk_size,
                        max_input_tokens=settings.max_llm_input_tokens,
                        llm_call_interval=settings.llm_call_interval,
                        content_language=settings.content_language,
                        quote_target_length=settings.review_quote_target_length,
                    )

            label = "idea" if total == 1 else "ideas"
            self.app.call_from_thread(self.notify, f"Reviewed {total} {label}.")
            self._load_data()
        except Exception as e:
            self.app.call_from_thread(self.notify, format_llm_error(e), severity="error")

    @work(thread=True)
    def _run_caption(self) -> None:
        from anne.db.connection import get_connection
        from anne.services.books import list_books
        from anne.services.ideas import get_ideas_by_status
        from anne.services.pipeline import caption_book_ideas, format_llm_error

        settings = self.app.settings
        api_key = settings.gemini_api_key
        if not api_key:
            self.app.call_from_thread(self.notify, "Gemini API key not configured", severity="error")
            return

        try:
            total = 0
            with get_connection(settings.db_path) as conn:
                books = list_books(conn)

            for book in books:
                with get_connection(settings.db_path) as conn:
                    reviewed_ideas = get_ideas_by_status(conn, book.id, IdeaStatus.reviewed)
                    if not reviewed_ideas:
                        continue
                    total += caption_book_ideas(
                        conn,
                        api_key=api_key,
                        book_title=book.title,
                        book_author=book.author,
                        ideas=reviewed_ideas,
                        chunk_size=settings.caption_chunk_size,
                        max_input_tokens=settings.max_llm_input_tokens,
                        llm_call_interval=settings.llm_call_interval,
                        content_language=settings.content_language,
                        cta_link=settings.cta_link,
                    )

            label = "idea" if total == 1 else "ideas"
            self.app.call_from_thread(self.notify, f"Captioned {total} {label}.")
            self._load_data()
        except Exception as e:
            self.app.call_from_thread(self.notify, format_llm_error(e), severity="error")
