from typing import Optional

import typer
from rich import print as rprint

from anne.config.settings import load_settings


def start_tui(
    book_slug: Optional[str] = typer.Argument(None, help="Book slug (omit for dashboard)"),
) -> None:
    """Open the TUI for browsing and editing ideas."""
    from anne.tui import AnneApp
    from anne.db.connection import get_connection
    from anne.utils.exceptions import WorkspaceAccessError

    settings = load_settings()

    try:
        if book_slug:
            from anne.services.books import get_book

            with get_connection(settings.db_path) as conn:
                book = get_book(conn, book_slug)
            if book is None:
                rprint(f"[red]Error:[/red] book not found: {book_slug}")
                raise typer.Exit(code=1)

            from anne.tui.screens.workspace import BookWorkspaceScreen

            class _DirectApp(AnneApp):
                def on_mount(self) -> None:
                    # Intentionally skips super().on_mount() to avoid pushing
                    # DashboardScreen — pressing q from workspace exits the app.
                    self.push_screen(BookWorkspaceScreen(book))

            app = _DirectApp(settings)
        else:
            # Probe the workspace DB before launching the TUI so a macOS
            # folder-access denial surfaces as clear guidance here instead of
            # crashing mid-render inside Textual. Only access denials abort
            # launch; benign errors (corruption, cloud eviction) are left for
            # the TUI to surface, to avoid regressing launch on them.
            try:
                with get_connection(settings.db_path):
                    pass
            except WorkspaceAccessError:
                raise
            except Exception:
                pass
            app = AnneApp(settings)
    except WorkspaceAccessError as exc:
        rprint(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    app.run()
