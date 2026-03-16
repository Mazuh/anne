import sqlite3
from pathlib import Path

import typer
from rich import print as rprint

from anne.config.settings import load_settings
from anne.db.connection import get_connection
from anne.models import Book, Source, SourceType
from anne.services.books import get_book, list_books
from anne.models import IdeaStatus
from anne.services.ideas import approve_idea, get_ideas_by_status, get_unparsed_sources, insert_ideas, reject_idea
from anne.services.parsers import ParsedIdea, parse_kindle_export_html, extract_html_content
from anne.services.llm import ContentTooLargeError, RateLimitError, parse_essay_with_llm, triage_ideas_with_llm

LLM_TYPES = {SourceType.essay_md, SourceType.essay_txt, SourceType.essay_html, SourceType.manual_notes}


def _parse_source(source: Source, content: str, api_key: str | None, max_input_tokens: int) -> list[ParsedIdea]:
    source_type = SourceType(source.type)
    if source_type == SourceType.kindle_export_html:
        return parse_kindle_export_html(content)
    elif source_type in LLM_TYPES:
        if not api_key:
            raise ValueError("gemini_api_key is required for LLM-assisted parsing")
        if source_type == SourceType.essay_html:
            content = extract_html_content(content)
        return parse_essay_with_llm(api_key, content, max_input_tokens=max_input_tokens)
    else:
        rprint(f"  [yellow]Warning:[/yellow] unknown source type '{source_type}', skipping")
        return []


def _parse_book(
    book: Book,
    books_dir: Path,
    api_key: str | None,
    conn: sqlite3.Connection,
    max_input_tokens: int,
) -> int:
    sources = get_unparsed_sources(conn, book.id)
    if not sources:
        rprint(f"  [dim]{book.title}: no unparsed sources[/dim]")
        return 0

    needs_llm = any(SourceType(s.type) in LLM_TYPES for s in sources)
    if needs_llm and not api_key:
        rprint(f"  [red]Error:[/red] {book.title} has essay/manual sources but gemini_api_key is not configured.")
        raise typer.Exit(code=1)

    total = 0
    for source in sources:
        source_path = books_dir / book.slug / source.path
        if not source_path.exists():
            rprint(f"  [red]Error:[/red] source file not found: {source_path}")
            continue
        rprint(f"  Parsing [cyan]{source.path}[/cyan]...")
        content = source_path.read_text(encoding="utf-8")
        ideas = _parse_source(source, content, api_key, max_input_tokens=max_input_tokens)
        if ideas:
            insert_ideas(conn, book.id, source.id, ideas)
        label = "idea" if len(ideas) == 1 else "ideas"
        rprint(f"  [green]{source.path}[/green]: {len(ideas)} {label} extracted")
        total += len(ideas)
    return total


def idea_parse(
    book_slug: str | None = typer.Argument(None, help="Book slug (omit to parse all books)"),
) -> None:
    """Parse sources into ideas."""
    settings = load_settings()
    api_key = settings.gemini_api_key

    with get_connection(settings.db_path) as conn:
        if book_slug:
            book = get_book(conn, book_slug)
            if book is None:
                rprint(f"[red]Error:[/red] book not found: {book_slug}")
                raise typer.Exit(code=1)
            books = [book]
        else:
            books = list_books(conn)

    grand_total = 0
    for book in books:
        rprint(f"[bold]{book.title}[/bold]")
        try:
            with get_connection(settings.db_path) as conn:
                grand_total += _parse_book(book, settings.books_dir, api_key, conn, settings.max_llm_input_tokens)
        except RateLimitError as e:
            rprint(f"  [red]Rate limited by Gemini API.[/red] Progress so far has been saved.")
            if str(e):
                rprint(f"  [dim]{e}[/dim]")
            rprint(f"  [dim]Wait a minute and run the command again to continue.[/dim]")
            raise typer.Exit(code=1)
        except ContentTooLargeError as e:
            rprint(f"  [red]Error:[/red] {e}")
            raise typer.Exit(code=1)

    rprint(f"\n[bold]Total: {grand_total} ideas parsed[/bold]")


def curation_triage(
    book_slug: str | None = typer.Argument(None, help="Book slug (omit to triage all books)"),
) -> None:
    """Triage parsed ideas: approve or reject using LLM."""
    settings = load_settings()
    api_key = settings.gemini_api_key
    if not api_key:
        rprint("[red]Error:[/red] gemini_api_key is not configured.")
        raise typer.Exit(code=1)

    with get_connection(settings.db_path) as conn:
        if book_slug:
            book = get_book(conn, book_slug)
            if book is None:
                rprint(f"[red]Error:[/red] book not found: {book_slug}")
                raise typer.Exit(code=1)
            books = [book]
        else:
            books = list_books(conn)

    total_approved = 0
    total_rejected = 0
    for book in books:
        rprint(f"[bold]{book.title}[/bold]")
        try:
            # One connection per book: commits after each book so progress is saved on rate-limit
            with get_connection(settings.db_path) as conn:
                parsed_ideas = get_ideas_by_status(conn, book.id, IdeaStatus.parsed)
                if not parsed_ideas:
                    rprint(f"  [dim]{book.title}: no parsed ideas to triage[/dim]")
                    continue

                chunks = [
                    parsed_ideas[i : i + settings.triage_chunk_size]
                    for i in range(0, len(parsed_ideas), settings.triage_chunk_size)
                ]
                for chunk in chunks:
                    decisions = triage_ideas_with_llm(
                        api_key=api_key,
                        book_title=book.title,
                        book_author=book.author,
                        ideas=chunk,
                        max_input_tokens=settings.max_llm_input_tokens,
                        min_interval=settings.llm_call_interval,
                    )
                    for d in decisions:
                        if d.decision == "approve":
                            approve_idea(conn, d.idea_id)
                            total_approved += 1
                            rprint(f"  [green]Approved[/green] idea {d.idea_id}")
                        elif d.decision == "reject":
                            reject_idea(conn, d.idea_id, d.rejection_reason)
                            total_rejected += 1
                            reason = f" — {d.rejection_reason}" if d.rejection_reason else ""
                            rprint(f"  [yellow]Rejected[/yellow] idea {d.idea_id}{reason}")
        except RateLimitError as e:
            rprint("  [red]Rate limited by Gemini API.[/red] Progress so far has been saved.")
            if str(e):
                rprint(f"  [dim]{e}[/dim]")
            rprint("  [dim]Wait a minute and run the command again to continue.[/dim]")
            raise typer.Exit(code=1)
        except ContentTooLargeError as e:
            rprint(f"  [red]Error:[/red] {e}")
            raise typer.Exit(code=1)

    rprint(f"\n[bold]Total: {total_approved} approved, {total_rejected} rejected[/bold]")
