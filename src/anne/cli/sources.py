import sqlite3
import tempfile
import urllib.error
from pathlib import Path

import typer
from rich import print as rprint
from rich.table import Table
from rich.console import Console

from anne.config.settings import Settings, load_settings
from anne.utils.icloud import ensure_available, is_icloud_evicted
from anne.db.connection import get_connection
from anne.models import Book, SourceType
from anne.services.books import get_book
from anne.services.sources import (
    compute_fingerprint,
    detect_duplicate,
    detect_source_type,
    fetch_url,
    import_source,
    is_url,
    list_sources,
)
from anne.services.filesystem import resolve_source_dest, copy_source_file

app = typer.Typer(help="Manage sources.")
console = Console()


@app.command("import")
def import_cmd(
    book_slug: str = typer.Argument(help="Book slug"),
    location: str = typer.Argument(help="Path to source file or URL"),
    type: SourceType | None = typer.Option(None, "--type", "-t", help="Source type (auto-detected if omitted)"),
) -> None:
    """Import a source file or URL for a book."""
    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        book = get_book(conn, book_slug)
        if book is None:
            rprint(f"[red]Error:[/red] book not found: {book_slug}")
            raise typer.Exit(code=1)

        if is_url(location):
            rprint(f"Fetching {location}...")
            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    fetched_path = fetch_url(location, Path(tmp_dir))
                    _do_import(conn, settings, book, fetched_path, type or SourceType.essay_html)
            except (urllib.error.URLError, OSError, ValueError) as e:
                rprint(f"[red]Error:[/red] failed to fetch URL: {e}")
                raise typer.Exit(code=1)
        else:
            file_path = Path(location).resolve()
            try:
                if is_icloud_evicted(file_path):
                    rprint("Downloading from cloud storage...")
                ensure_available(file_path)
            except FileNotFoundError:
                rprint(f"[red]Error:[/red] file not found: {location}")
                raise typer.Exit(code=1)
            source_type = type if type is not None else detect_source_type(file_path)
            _do_import(conn, settings, book, file_path, source_type)


def _do_import(conn: sqlite3.Connection, settings: Settings, book: Book, file_path: Path, source_type: SourceType) -> None:
    fingerprint = compute_fingerprint(file_path)

    if detect_duplicate(conn, book.id, fingerprint):
        rprint(f"[yellow]Skipped:[/yellow] source already imported (same fingerprint).")
        return

    dest = resolve_source_dest(settings.books_dir, book.slug, source_type, file_path.name)
    copy_source_file(file_path, dest)

    relative_path = str(dest.relative_to(settings.books_dir / book.slug))
    source = import_source(conn, book.id, source_type, relative_path, fingerprint)
    rprint(f"[green]Imported:[/green] {file_path.name} as {source_type.value} (id: {source.id})")


@app.command("list")
def list_cmd(
    book_slug: str = typer.Argument(help="Book slug"),
) -> None:
    """List sources for a book."""
    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        book = get_book(conn, book_slug)
        if book is None:
            rprint(f"[red]Error:[/red] book not found: {book_slug}")
            raise typer.Exit(code=1)

        sources = list_sources(conn, book.id)
        if not sources:
            rprint("No sources found for this book.")
            return

        table = Table(title=f"Sources for {book.title}")
        table.add_column("ID", justify="right")
        table.add_column("Type")
        table.add_column("Path")
        table.add_column("Imported")

        for s in sources:
            table.add_row(str(s.id), s.type, s.path, s.imported_at)

        console.print(table)
