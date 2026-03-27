import typer
from rich import print as rprint
from rich.table import Table
from rich.console import Console

from anne.config.settings import load_settings
from anne.db.connection import get_connection
from anne.services.books import create_book, list_books, get_book, get_book_stats, DuplicateBookError
from anne.services.filesystem import create_book_dirs

app = typer.Typer(help="Manage books.")
console = Console()


@app.command()
def add(
    title: str = typer.Argument(help="Book title"),
    author: str = typer.Option("", help="Book author"),
) -> None:
    """Add a new book."""
    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        try:
            book = create_book(conn, title, author)
        except DuplicateBookError as e:
            rprint(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1)
        create_book_dirs(settings.books_dir, book.slug)
        rprint(f"[green]Book created:[/green] {book.title} ({book.slug})")


@app.command("list")
def list_cmd() -> None:
    """List all books."""
    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        books = list_books(conn)
        if not books:
            rprint("No books found. Add one with [bold]anne books add[/bold].")
            return

        table = Table(title="Books")
        table.add_column("Slug")
        table.add_column("Title")
        table.add_column("Author")
        table.add_column("Sources", justify="right")
        table.add_column("Ideas", justify="right")

        for book in books:
            stats = get_book_stats(conn, book.id)
            table.add_row(
                book.slug,
                book.title,
                book.author,
                str(stats["sources"]),
                str(stats["ideas_total"]),
            )

        console.print(table)


@app.command()
def show(slug: str = typer.Argument(help="Book slug")) -> None:
    """Show details for a book."""
    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        book = get_book(conn, slug)
        if book is None:
            rprint(f"[red]Error:[/red] book not found: {slug}")
            raise typer.Exit(code=1)

        stats = get_book_stats(conn, book.id)

        rprint(f"[bold]{book.title}[/bold]")
        rprint(f"  Author: {book.author or '(none)'}")
        rprint(f"  Slug:   {book.slug}")
        rprint(f"  Created: {book.created_at}")
        rprint(f"\n  Sources: {stats['sources']}")

        if stats["ideas"]:
            rprint("\n  Ideas by status:")
            for status, count in sorted(stats["ideas"].items()):
                rprint(f"    {status}: {count}")
        else:
            rprint("  Ideas: 0")
