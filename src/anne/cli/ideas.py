import sqlite3
from pathlib import Path

import typer
from rich import print as rprint
from rich.markup import escape

from anne.config.settings import load_settings
from anne.db.connection import get_connection
from anne.models import Book, Idea, IdeaStatus, Source, SourceType
from anne.services.books import get_book, list_books
from anne.services.ideas import approve_idea, get_ideas_by_status, get_unparsed_sources, insert_ideas, reject_idea, review_idea
from anne.services.parsers import ParsedIdea, parse_kindle_export_html, extract_html_content
from anne.services.llm import ContentTooLargeError, RateLimitError, parse_essay_with_llm, triage_ideas_with_llm, review_ideas_with_llm

LLM_TYPES = {SourceType.essay_md, SourceType.essay_txt, SourceType.essay_html, SourceType.manual_notes}

_MAX_PREVIEW_LEN = 80


def _idea_preview(idea: Idea) -> str:
    text = idea.raw_quote or idea.raw_note
    if not text:
        return ""
    label = "Quote" if idea.raw_quote else "Comment"
    truncated = text[:_MAX_PREVIEW_LEN] + "..." if len(text) > _MAX_PREVIEW_LEN else text
    return f' — {label}: "{escape(truncated)}"'


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


def idea_triage(
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
                        total_ideas=len(parsed_ideas),
                        max_input_tokens=settings.max_llm_input_tokens,
                        min_interval=settings.llm_call_interval,
                    )
                    ideas_by_id = {idea.id: idea for idea in chunk}
                    for d in decisions:
                        idea = ideas_by_id.get(d.idea_id)
                        if d.decision == "approve":
                            approve_idea(conn, d.idea_id)
                            total_approved += 1
                            preview = _idea_preview(idea) if idea else ""
                            rprint(f"  [green]Approved[/green] idea {d.idea_id}{preview}")
                        elif d.decision == "reject":
                            reject_idea(conn, d.idea_id, d.rejection_reason)
                            total_rejected += 1
                            reason = f" — {d.rejection_reason}" if d.rejection_reason else ""
                            rprint(f"  [yellow]Rejected[/yellow] idea {d.idea_id}{reason}")
                    conn.commit()
        except RateLimitError as e:
            rprint("  [red]Rate limited by Gemini API.[/red] Progress so far has been saved.")
            if str(e):
                rprint(f"  [dim]{e}[/dim]")
            rprint("  [dim]Wait a minute and run the command again to continue.[/dim]")
            raise typer.Exit(code=1)
        except ContentTooLargeError as e:
            rprint(f"  [red]Error:[/red] {e}")
            raise typer.Exit(code=1)

    label = "idea" if total_approved + total_rejected == 1 else "ideas"
    rprint(f"\n[bold]Total: {total_approved} approved, {total_rejected} rejected ({total_approved + total_rejected} {label})[/bold]")


def idea_review(
    book_slug: str | None = typer.Argument(None, help="Book slug (omit to review all books)"),
) -> None:
    """Review approved ideas: refine quotes and add factual context using LLM."""
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

    total_reviewed = 0
    for book in books:
        rprint(f"[bold]{book.title}[/bold]")
        try:
            with get_connection(settings.db_path) as conn:
                approved_ideas = get_ideas_by_status(conn, book.id, IdeaStatus.approved)
                if not approved_ideas:
                    rprint(f"  [dim]{book.title}: no approved ideas to review[/dim]")
                    continue

                chunks = [
                    approved_ideas[i : i + settings.review_chunk_size]
                    for i in range(0, len(approved_ideas), settings.review_chunk_size)
                ]
                for chunk in chunks:
                    results = review_ideas_with_llm(
                        api_key=api_key,
                        book_title=book.title,
                        book_author=book.author,
                        ideas=chunk,
                        content_language=settings.content_language,
                        quote_target_length=settings.review_quote_target_length,
                        max_input_tokens=settings.max_llm_input_tokens,
                        min_interval=settings.llm_call_interval,
                    )
                    for r in results:
                        review_idea(
                            conn,
                            r.idea_id,
                            r.reviewed_quote,
                            r.reviewed_quote_emphasis,
                            r.reviewed_comment,
                        )
                        total_reviewed += 1
                        preview = r.reviewed_quote[:_MAX_PREVIEW_LEN]
                        if len(r.reviewed_quote) > _MAX_PREVIEW_LEN:
                            preview += "..."
                        rprint(f'  [green]Reviewed[/green] idea {r.idea_id} — Quote: "{escape(preview)}"')
                    conn.commit()
        except RateLimitError as e:
            rprint("  [red]Rate limited by Gemini API.[/red] Progress so far has been saved.")
            if str(e):
                rprint(f"  [dim]{e}[/dim]")
            rprint("  [dim]Wait a minute and run the command again to continue.[/dim]")
            raise typer.Exit(code=1)
        except ContentTooLargeError as e:
            rprint(f"  [red]Error:[/red] {e}")
            raise typer.Exit(code=1)

    label = "idea" if total_reviewed == 1 else "ideas"
    rprint(f"\n[bold]Total: {total_reviewed} {label} reviewed[/bold]")
