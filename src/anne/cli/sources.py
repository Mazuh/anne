from pathlib import Path

import typer
from rich import print as rprint
from rich.table import Table
from rich.console import Console

from anne.config.settings import load_settings
from anne.db.connection import get_connection
from anne.models import SourceType
from anne.services.books import get_book
from anne.services.sources import (
    compute_fingerprint,
    detect_duplicate,
    detect_source_type,
    import_source,
    list_sources,
)
from anne.services.filesystem import resolve_source_dest, copy_source_file

app = typer.Typer(help="Manage sources.")
console = Console()


@app.command("import")
def import_cmd(
    book_slug: str = typer.Argument(help="Book slug"),
    file_path: Path = typer.Argument(help="Path to source file", exists=True),
    type: SourceType | None = typer.Option(None, "--type", "-t", help="Source type (auto-detected if omitted)"),
) -> None:
    """Import a source file for a book."""
    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        book = get_book(conn, book_slug)
        if book is None:
            rprint(f"[red]Error:[/red] book not found: {book_slug}")
            raise typer.Exit(code=1)

        file_path = file_path.resolve()
        fingerprint = compute_fingerprint(file_path)

        if detect_duplicate(conn, book.id, fingerprint):
            rprint(f"[yellow]Skipped:[/yellow] file already imported (same fingerprint).")
            return

        source_type = type if type is not None else detect_source_type(file_path)
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
