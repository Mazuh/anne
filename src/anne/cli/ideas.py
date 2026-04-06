import json
import math
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from anne.config.settings import load_settings
from anne.utils.icloud import ensure_available, is_icloud_evicted
from anne.db.connection import get_connection
from anne.models import Book, Idea, IdeaStatus, STABLE_STATUSES, Source, SourceType
from anne.services.books import get_book, get_book_by_id, get_book_titles, list_books
from anne.services.sources import get_source
from anne.services.ideas import (
    triage_approve_idea,
    caption_idea,
    count_ideas,
    get_commented_ideas,
    get_idea,
    get_ideas_by_status,
    get_random_stable_idea,
    get_sample_quotes_by_tag,
    get_tags_with_counts,
    get_unparsed_sources,
    insert_ideas,
    insert_manual_idea,
    list_ideas_paginated,
    publish_idea,
    queue_idea,
    reject_idea,
    review_idea,
    update_idea,
)
from anne.services.parsers import LLM_TYPES, ParsedIdea, parse_kindle_export_html, extract_html_content, parse_source
from anne.services.llm import (
    ContentTooLargeError,
    RateLimitError,
    TruncatedResponseError,
    caption_ideas_with_llm,
    custom_prompt_idea,
    digest_notes_with_llm,
    generate_curiosity_phrase,
    generate_video_prompts,
    parse_essay_with_llm,
    review_ideas_with_llm,
    synthesize_digest_with_llm,
    triage_ideas_with_llm,
)

ideas_app = typer.Typer(help="Browse and manage ideas.")
console = Console()

_MAX_PREVIEW_LEN = 80


def _idea_preview(idea: Idea) -> str:
    text = idea.raw_quote or idea.raw_note
    if not text:
        return ""
    label = "Quote" if idea.raw_quote else "Comment"
    truncated = text[:_MAX_PREVIEW_LEN] + "..." if len(text) > _MAX_PREVIEW_LEN else text
    return f' — {label}: "{escape(truncated)}"'


_LIST_PREVIEW_LEN = 60


def _truncate(text: str | None, length: int = _LIST_PREVIEW_LEN) -> str:
    if not text:
        return ""
    return text[:length] + "…" if len(text) > length else text


@ideas_app.command("list")
def list_cmd(
    book_slug: Optional[str] = typer.Argument(None, help="Book slug (omit to list all books)"),
    status: Optional[IdeaStatus] = typer.Option(None, help="Filter by status"),
    page: int = typer.Option(1, help="Page number"),
    per_page: int = typer.Option(25, help="Items per page"),
) -> None:
    """List ideas with optional filters and pagination."""
    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        book: Book | None = None
        book_id: int | None = None
        if book_slug:
            book = get_book(conn, book_slug)
            if book is None:
                rprint(f"[red]Error:[/red] book not found: {book_slug}")
                raise typer.Exit(code=1)
            book_id = book.id

        total = count_ideas(conn, book_id=book_id, status=status)
        if total == 0:
            rprint("No ideas found.")
            return

        total_pages = math.ceil(total / per_page)
        if page > total_pages:
            rprint(f"[red]Error:[/red] page {page} exceeds total pages ({total_pages})")
            raise typer.Exit(code=1)

        ideas = list_ideas_paginated(conn, book_id=book_id, status=status, page=page, per_page=per_page)

        # Build title
        title_parts = ["Ideas"]
        if book:
            title_parts.append(f'for "{book.title}"')
        if status:
            title_parts.append(f"({status.value})")
        title_parts.append(f"— Page {page}/{total_pages}")
        title = " ".join(title_parts)

        table = Table(title=title)
        table.add_column("ID", justify="right")
        table.add_column("Status")
        if not book_slug:
            books_by_id = get_book_titles(conn)
            table.add_column("Book")
        table.add_column("Quote/Note")
        table.add_column("Ref")
        table.add_column("Updated")

        for idea in ideas:
            preview = _truncate(idea.raw_quote or idea.raw_note)
            row: list[str] = [str(idea.id), idea.status]
            if not book_slug:
                row.append(books_by_id.get(idea.book_id, "?"))
            row.extend([preview, idea.raw_ref or "", idea.updated_at or ""])
            table.add_row(*row)

        console.print(table)
        rprint(f"Page {page}/{total_pages} ({total} total ideas)")


@ideas_app.command("tags")
def tags_cmd(
    book_slug: Optional[str] = typer.Argument(None, help="Book slug (omit to list tags across all books)"),
) -> None:
    """List all tags ordered by usage count."""
    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        book: Book | None = None
        book_id: int | None = None
        if book_slug:
            book = get_book(conn, book_slug)
            if book is None:
                rprint(f"[red]Error:[/red] book not found: {book_slug}")
                raise typer.Exit(code=1)
            book_id = book.id

        results = get_tags_with_counts(conn, book_id=book_id)
        if not results:
            rprint("No tags found.")
            return

        title_parts = ["Tags"]
        if book:
            title_parts.append(f'for "{book.title}"')
        title = " ".join(title_parts)

        table = Table(title=title)
        table.add_column("Tag")
        table.add_column("Count", justify="right")
        for tag, count in results:
            table.add_row(tag, str(count))

        console.print(table)
        rprint(f"{len(results)} distinct tags")


@ideas_app.command()
def show(
    idea_id: int = typer.Argument(help="Idea ID"),
) -> None:
    """Show full details of a single idea."""
    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        idea = get_idea(conn, idea_id)
        if idea is None:
            rprint(f"[red]Error:[/red] idea not found: {idea_id}")
            raise typer.Exit(code=1)

        # Get book title and source path
        idea_book = get_book_by_id(conn, idea.book_id)
        book_title = idea_book.title if idea_book else "?"
        idea_source = get_source(conn, idea.source_id)
        source_path = idea_source.path if idea_source else "?"

        # Header
        rprint(f"[bold]Idea #{idea.id}[/bold]  [{idea.status}]")
        rprint(f"  Book:    {book_title}")
        rprint(f"  Source:  {source_path}")
        if idea.raw_ref:
            rprint(f"  Ref:     {idea.raw_ref}")
        rprint(f"  Created: {idea.created_at}")
        rprint(f"  Updated: {idea.updated_at}")
        if idea.published_at:
            rprint(f"  Published: {idea.published_at}")

        # Raw
        if idea.raw_quote or idea.raw_note:
            rprint(f"\n[bold]Raw[/bold]")
            if idea.raw_quote:
                rprint(f'  Quote: "{escape(idea.raw_quote)}"')
            if idea.raw_note:
                rprint(f"  Note:  {escape(idea.raw_note)}")

        # Triage
        if idea.status == IdeaStatus.rejected and idea.rejection_reason:
            rprint(f"\n[bold]Triage[/bold]")
            rprint(f"  Rejection reason: {escape(idea.rejection_reason)}")

        # Review
        if idea.reviewed_quote or idea.reviewed_comment:
            rprint(f"\n[bold]Review[/bold]")
            if idea.reviewed_quote:
                rprint(f'  Quote:    "{escape(idea.reviewed_quote)}"')
            if idea.reviewed_comment:
                rprint(f"  Comment:  {escape(idea.reviewed_comment)}")

        # Caption
        if idea.presentation_text or (idea.tags and idea.tags != "[]"):
            rprint(f"\n[bold]Caption[/bold]")
            if idea.presentation_text:
                rprint(f"  Text: {escape(idea.presentation_text)}")
            if idea.tags and idea.tags != "[]":
                rprint(f"  Tags: {idea.tags}")


@ideas_app.command()
def edit(
    idea_id: int = typer.Argument(help="Idea ID"),
    status: Optional[IdeaStatus] = typer.Option(None, help="New status"),
    raw_quote: Optional[str] = typer.Option(None, help="Update raw_quote"),
    raw_note: Optional[str] = typer.Option(None, help="Update raw_note"),
    reviewed_quote: Optional[str] = typer.Option(None, help="Update reviewed_quote"),
    reviewed_comment: Optional[str] = typer.Option(None, help="Update reviewed_comment"),
    presentation_text: Optional[str] = typer.Option(None, help="Update presentation_text"),
    rejection_reason: Optional[str] = typer.Option(None, help="Update rejection_reason"),
    tags: Optional[str] = typer.Option(None, help="Update tags (JSON array)"),
    force: bool = typer.Option(False, help="Skip status transition validation"),
) -> None:
    """Edit idea fields directly."""
    fields: dict[str, object] = {}
    if status is not None:
        fields["status"] = status.value
    if raw_quote is not None:
        fields["raw_quote"] = raw_quote
    if raw_note is not None:
        fields["raw_note"] = raw_note
    if reviewed_quote is not None:
        fields["reviewed_quote"] = reviewed_quote
    if reviewed_comment is not None:
        fields["reviewed_comment"] = reviewed_comment
    if presentation_text is not None:
        fields["presentation_text"] = presentation_text
    if rejection_reason is not None:
        fields["rejection_reason"] = rejection_reason
    if tags is not None:
        fields["tags"] = tags

    if not fields:
        rprint("[red]Error:[/red] at least one field must be provided")
        raise typer.Exit(code=1)

    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        try:
            updated = update_idea(conn, idea_id, force=force, **fields)
        except ValueError as e:
            rprint(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1)

    rprint(f"[green]Updated idea {updated.id}[/green] — status: {updated.status}")
    preview = _truncate(updated.reviewed_quote or updated.raw_quote or updated.raw_note, _MAX_PREVIEW_LEN)
    if preview:
        rprint(f'  "{escape(preview)}"')


@ideas_app.command()
def add(
    book_slug: str = typer.Argument(help="Book slug"),
    raw_quote: Optional[str] = typer.Option(None, "--raw-quote", help="Verbatim quote"),
    raw_note: Optional[str] = typer.Option(None, "--raw-note", help="Your own note"),
    ref: Optional[str] = typer.Option(None, "--ref", help="Reference (page, chapter, etc.)"),
) -> None:
    """Manually add an idea to a book (starts as triaged)."""
    if not (raw_quote and raw_quote.strip()) and not (raw_note and raw_note.strip()):
        rprint("[red]Error:[/red] at least one of --raw-quote or --raw-note is required")
        raise typer.Exit(code=1)

    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        book = get_book(conn, book_slug)
        if book is None:
            rprint(f"[red]Error:[/red] book not found: {book_slug}")
            raise typer.Exit(code=1)

        idea = insert_manual_idea(conn, book.id, raw_quote, raw_note, ref)

    rprint(f"[green]Added idea {idea.id}[/green] — status: {idea.status}")
    preview = _truncate(idea.raw_quote or idea.raw_note, _MAX_PREVIEW_LEN)
    if preview:
        rprint(f'  "{escape(preview)}"')


def _parse_source(source: Source, content: str, api_key: str | None, max_input_tokens: int) -> list[ParsedIdea]:
    ideas = parse_source(source, content, api_key, max_input_tokens)
    if ideas is None:
        rprint(f"  [yellow]Warning:[/yellow] unknown source type '{source.type}', skipping")
        return []
    return ideas


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
        try:
            if is_icloud_evicted(source_path):
                rprint(f"  Downloading from cloud storage: [cyan]{source.path}[/cyan]...")
            ensure_available(source_path)
        except FileNotFoundError:
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


@ideas_app.command("parse")
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
        except TimeoutError as e:
            rprint("  [red]API request timed out.[/red] Progress so far has been saved.")
            rprint(f"  [dim]{e}[/dim]")
            rprint("  [dim]Run the command again to continue.[/dim]")
            raise typer.Exit(code=1)
        except (ContentTooLargeError, TruncatedResponseError) as e:
            rprint(f"  [red]Error:[/red] {e}")
            raise typer.Exit(code=1)

    rprint(f"\n[bold]Total: {grand_total} ideas parsed[/bold]")


@ideas_app.command("triage")
def idea_triage(
    book_slug: str | None = typer.Argument(None, help="Book slug (omit to triage all books)"),
) -> None:
    """Triage parsed ideas: triage or reject using LLM."""
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

    total_triaged = 0
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
                        if d.decision == "triage":
                            triage_approve_idea(conn, d.idea_id)
                            total_triaged += 1
                            preview = _idea_preview(idea) if idea else ""
                            rprint(f"  [green]Triaged[/green] idea {d.idea_id}{preview}")
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
        except TimeoutError as e:
            rprint("  [red]API request timed out.[/red] Progress so far has been saved.")
            rprint(f"  [dim]{e}[/dim]")
            rprint("  [dim]Run the command again to continue.[/dim]")
            raise typer.Exit(code=1)
        except (ContentTooLargeError, TruncatedResponseError) as e:
            rprint(f"  [red]Error:[/red] {e}")
            raise typer.Exit(code=1)

    label = "idea" if total_triaged + total_rejected == 1 else "ideas"
    rprint(f"\n[bold]Total: {total_triaged} triaged, {total_rejected} rejected ({total_triaged + total_rejected} {label})[/bold]")


@ideas_app.command("review")
def idea_review(
    book_slug: str | None = typer.Argument(None, help="Book slug (omit to review all books)"),
    redo: bool = typer.Option(False, "--redo", help="Re-review ideas already in reviewed status"),
) -> None:
    """Review triaged ideas: refine quotes and add factual context using LLM."""
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
                ideas_to_review = get_ideas_by_status(conn, book.id, IdeaStatus.triaged)
                if redo:
                    ideas_to_review += get_ideas_by_status(conn, book.id, IdeaStatus.reviewed)
                if not ideas_to_review:
                    rprint(f"  [dim]{book.title}: no ideas to review[/dim]")
                    continue

                chunks = [
                    ideas_to_review[i : i + settings.review_chunk_size]
                    for i in range(0, len(ideas_to_review), settings.review_chunk_size)
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
                            r.reviewed_comment,
                            allow_reviewed=redo,
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
        except TimeoutError as e:
            rprint("  [red]API request timed out.[/red] Progress so far has been saved.")
            rprint(f"  [dim]{e}[/dim]")
            rprint("  [dim]Run the command again to continue.[/dim]")
            raise typer.Exit(code=1)
        except (ContentTooLargeError, TruncatedResponseError) as e:
            rprint(f"  [red]Error:[/red] {e}")
            raise typer.Exit(code=1)

    label = "idea" if total_reviewed == 1 else "ideas"
    rprint(f"\n[bold]Total: {total_reviewed} {label} reviewed[/bold]")


@ideas_app.command("caption")
def idea_caption(
    book_slug: str | None = typer.Argument(None, help="Book slug (omit to caption all books)"),
) -> None:
    """Generate Instagram captions for reviewed ideas using LLM."""
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

    total_captioned = 0
    for book in books:
        rprint(f"[bold]{book.title}[/bold]")
        try:
            with get_connection(settings.db_path) as conn:
                reviewed_ideas = get_ideas_by_status(conn, book.id, IdeaStatus.reviewed)
                if not reviewed_ideas:
                    rprint(f"  [dim]{book.title}: no reviewed ideas to caption[/dim]")
                    continue

                chunks = [
                    reviewed_ideas[i : i + settings.caption_chunk_size]
                    for i in range(0, len(reviewed_ideas), settings.caption_chunk_size)
                ]
                for chunk in chunks:
                    results = caption_ideas_with_llm(
                        api_key=api_key,
                        book_title=book.title,
                        book_author=book.author,
                        ideas=chunk,
                        content_language=settings.content_language,
                        cta_link=settings.cta_link,
                        max_input_tokens=settings.max_llm_input_tokens,
                        min_interval=settings.llm_call_interval,
                    )
                    for r in results:
                        caption_idea(
                            conn,
                            r.idea_id,
                            r.presentation_text,
                            json.dumps(r.tags, ensure_ascii=False),
                        )
                        total_captioned += 1
                        preview = r.presentation_text[:_MAX_PREVIEW_LEN]
                        if len(r.presentation_text) > _MAX_PREVIEW_LEN:
                            preview += "..."
                        rprint(f'  [green]Captioned[/green] idea {r.idea_id} — "{escape(preview)}"')
                    conn.commit()
        except RateLimitError as e:
            rprint("  [red]Rate limited by Gemini API.[/red] Progress so far has been saved.")
            if str(e):
                rprint(f"  [dim]{e}[/dim]")
            rprint("  [dim]Wait a minute and run the command again to continue.[/dim]")
            raise typer.Exit(code=1)
        except TimeoutError as e:
            rprint("  [red]API request timed out.[/red] Progress so far has been saved.")
            rprint(f"  [dim]{e}[/dim]")
            rprint("  [dim]Run the command again to continue.[/dim]")
            raise typer.Exit(code=1)
        except (ContentTooLargeError, TruncatedResponseError) as e:
            rprint(f"  [red]Error:[/red] {e}")
            raise typer.Exit(code=1)

    label = "idea" if total_captioned == 1 else "ideas"
    rprint(f"\n[bold]Total: {total_captioned} {label} captioned[/bold]")


@ideas_app.command("publish")
def idea_publish(
    idea_id: int = typer.Argument(help="Idea ID to mark as published"),
) -> None:
    """Mark a ready or queued idea as published (flag only, actual publishing is manual)."""
    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        idea = get_idea(conn, idea_id)
        if idea is None:
            rprint(f"[red]Error:[/red] idea not found: {idea_id}")
            raise typer.Exit(code=1)

        if idea.status not in (IdeaStatus.ready, IdeaStatus.queued):
            rprint(
                f"[red]Error:[/red] idea {idea_id} is '{idea.status}', must be 'ready' or 'queued' to publish."
            )
            raise typer.Exit(code=1)

        quote = idea.reviewed_quote or idea.raw_quote
        comment = idea.reviewed_comment or idea.raw_note
        rprint(f"\n[bold]Idea #{idea.id}[/bold]")
        if quote:
            rprint(f'  [dim]Quote:[/dim]   "{escape(quote)}"')
        if comment:
            rprint(f"  [dim]Comment:[/dim] {escape(comment)}")
        rprint()

        typer.confirm("Are you sure you want to publish this idea?", abort=True)

        published = publish_idea(conn, idea_id)

    rprint(f"[green]Published idea #{published.id}.[/green]")


@ideas_app.command("queue")
def idea_queue(
    idea_id: int = typer.Argument(help="Idea ID to mark as queued"),
) -> None:
    """Mark a ready idea as queued (visual flag only, no actual scheduling)."""
    settings = load_settings()
    with get_connection(settings.db_path) as conn:
        idea = get_idea(conn, idea_id)
        if idea is None:
            rprint(f"[red]Error:[/red] idea not found: {idea_id}")
            raise typer.Exit(code=1)

        if idea.status != IdeaStatus.ready:
            rprint(
                f"[red]Error:[/red] idea {idea_id} is '{idea.status}', must be 'ready' to queue."
            )
            raise typer.Exit(code=1)

        quote = idea.reviewed_quote or idea.raw_quote
        comment = idea.reviewed_comment or idea.raw_note
        rprint(f"\n[bold]Idea #{idea.id}[/bold]")
        if quote:
            rprint(f'  [dim]Quote:[/dim]   "{escape(quote)}"')
        if comment:
            rprint(f"  [dim]Comment:[/dim] {escape(comment)}")
        rprint()

        typer.confirm("Mark this idea as queued?", abort=True)

        queued = queue_idea(conn, idea_id)

    rprint(f"[green]Queued idea #{queued.id}.[/green]")


@ideas_app.command("prompt")
def idea_prompt(
    idea_id: int = typer.Argument(help="Idea ID"),
    prompt_text: str = typer.Option(..., "--prompt", "-p", help="Custom prompt/instruction for the LLM"),
) -> None:
    """Send a custom prompt about a stable idea to the LLM (one-shot, no storage)."""
    settings = load_settings()
    api_key = settings.gemini_api_key
    if not api_key:
        rprint("[red]Error:[/red] gemini_api_key is not configured.")
        raise typer.Exit(code=1)

    with get_connection(settings.db_path) as conn:
        idea = get_idea(conn, idea_id)
        if idea is None:
            rprint(f"[red]Error:[/red] idea not found: {idea_id}")
            raise typer.Exit(code=1)

        if idea.status not in STABLE_STATUSES:
            stable_names = ", ".join(sorted(s.value for s in STABLE_STATUSES))
            rprint(
                f"[red]Error:[/red] idea {idea_id} is '{idea.status}', "
                f"must be one of: {stable_names}."
            )
            raise typer.Exit(code=1)

        if not idea.reviewed_quote:
            rprint(f"[red]Error:[/red] idea {idea_id} is missing reviewed_quote.")
            raise typer.Exit(code=1)

    try:
        response = custom_prompt_idea(
            api_key=api_key,
            reviewed_quote=idea.reviewed_quote,
            prompt_text=prompt_text,
            content_language=settings.content_language,
            min_interval=settings.llm_call_interval,
            presentation_text=idea.presentation_text or "",
        )
    except RateLimitError as e:
        rprint("  [red]Rate limited by Gemini API.[/red]")
        if str(e):
            rprint(f"  [dim]{e}[/dim]")
        rprint("  [dim]Wait a minute and run the command again.[/dim]")
        raise typer.Exit(code=1)
    except TimeoutError as e:
        rprint("  [red]API request timed out.[/red]")
        rprint(f"  [dim]{e}[/dim]")
        rprint("  [dim]Run the command again to retry.[/dim]")
        raise typer.Exit(code=1)
    except (ContentTooLargeError, TruncatedResponseError) as e:
        rprint(f"  [red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    rprint(f"\n{response}")


@ideas_app.command("curiosity")
def idea_curiosity(
    idea_id: Optional[int] = typer.Argument(None, help="Idea ID (omit for random stable idea)"),
    book_slug: Optional[str] = typer.Option(None, "--book", "-b", help="Scope random selection to a book"),
) -> None:
    """Generate a curiosity-inducing phrase from an idea's raw quote."""
    settings = load_settings()
    api_key = settings.gemini_api_key
    if not api_key:
        rprint("[red]Error:[/red] gemini_api_key is not configured.")
        raise typer.Exit(code=1)

    with get_connection(settings.db_path) as conn:
        if idea_id is not None:
            idea = get_idea(conn, idea_id)
            if idea is None:
                rprint(f"[red]Error:[/red] idea not found: {idea_id}")
                raise typer.Exit(code=1)
            if idea.status not in STABLE_STATUSES:
                stable_names = ", ".join(sorted(s.value for s in STABLE_STATUSES))
                rprint(
                    f"[red]Error:[/red] idea {idea_id} is '{idea.status}', "
                    f"must be one of: {stable_names}."
                )
                raise typer.Exit(code=1)
        else:
            book_id: int | None = None
            if book_slug:
                book = get_book(conn, book_slug)
                if book is None:
                    rprint(f"[red]Error:[/red] book not found: {book_slug}")
                    raise typer.Exit(code=1)
                book_id = book.id
            idea = get_random_stable_idea(conn, book_id=book_id)
            if idea is None:
                scope = f" for book '{book_slug}'" if book_slug else ""
                rprint(f"[red]Error:[/red] no stable ideas found{scope}.")
                raise typer.Exit(code=1)

        if not idea.raw_quote:
            rprint(f"[red]Error:[/red] idea {idea.id} has no raw_quote.")
            raise typer.Exit(code=1)

    try:
        curiosity = generate_curiosity_phrase(
            api_key=api_key,
            raw_quote=idea.raw_quote,
            content_language=settings.content_language,
            min_interval=settings.llm_call_interval,
        )
    except RateLimitError as e:
        rprint("  [red]Rate limited by Gemini API.[/red]")
        if str(e):
            rprint(f"  [dim]{e}[/dim]")
        rprint("  [dim]Wait a minute and run the command again.[/dim]")
        raise typer.Exit(code=1)
    except TimeoutError as e:
        rprint("  [red]API request timed out.[/red]")
        rprint(f"  [dim]{e}[/dim]")
        rprint("  [dim]Run the command again to retry.[/dim]")
        raise typer.Exit(code=1)
    except (ContentTooLargeError, TruncatedResponseError) as e:
        rprint(f"  [red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    rprint(f"\n[bold]Idea #{idea.id}[/bold]\n")
    rprint(f"{curiosity}\n")
    rprint("[dim]---[/dim]")
    if idea.reviewed_quote:
        rprint(f'[dim]Reviewed quote:[/dim]   "{escape(idea.reviewed_quote)}"')
    if idea.reviewed_comment:
        rprint(f"[dim]Reviewed comment:[/dim] {escape(idea.reviewed_comment)}")
    if idea.presentation_text:
        rprint(f"[dim]Caption:[/dim]          {escape(idea.presentation_text)}")


@ideas_app.command("digest-notes")
def idea_digest_notes(
    book_slug: str = typer.Argument(help="Book slug"),
) -> None:
    """Generate a thematic digest of your annotated ideas to help prepare a literary essay."""
    from datetime import datetime

    settings = load_settings()
    api_key = settings.gemini_api_key
    if not api_key:
        rprint("[red]Error:[/red] gemini_api_key is not configured.")
        raise typer.Exit(code=1)

    with get_connection(settings.db_path) as conn:
        book = get_book(conn, book_slug)
        if book is None:
            rprint(f"[red]Error:[/red] book not found: {book_slug}")
            raise typer.Exit(code=1)

        ideas = get_commented_ideas(conn, book.id)

    if not ideas:
        rprint(f"No triaged+ ideas with comments found for [bold]{book.title}[/bold].")
        rprint("[dim]Ideas need a raw_note (your own comment/annotation) and be at least triaged.[/dim]")
        raise typer.Exit(code=1)

    label = "idea" if len(ideas) == 1 else "ideas"
    rprint(f"[bold]{book.title}[/bold] — {len(ideas)} commented {label} to digest")

    try:
        chunks = [
            ideas[i : i + settings.digest_chunk_size]
            for i in range(0, len(ideas), settings.digest_chunk_size)
        ]

        chunk_digests: list[str] = []
        for idx, chunk in enumerate(chunks):
            if len(chunks) > 1:
                rprint(f"  Processing chunk {idx + 1}/{len(chunks)} ({len(chunk)} ideas)...")
            digest = digest_notes_with_llm(
                api_key=api_key,
                book_title=book.title,
                book_author=book.author,
                ideas=chunk,
                content_language=settings.content_language,
                max_input_tokens=settings.max_llm_input_tokens,
                min_interval=settings.llm_call_interval,
            )
            chunk_digests.append(digest)

        if len(chunk_digests) > 1:
            rprint("  Synthesizing all chunks into a single digest...")
            final_digest = synthesize_digest_with_llm(
                api_key=api_key,
                book_title=book.title,
                book_author=book.author,
                chunk_digests=chunk_digests,
                content_language=settings.content_language,
                min_interval=settings.llm_call_interval,
            )
        else:
            final_digest = chunk_digests[0]

    except RateLimitError as e:
        rprint("  [red]Rate limited by Gemini API.[/red]")
        if str(e):
            rprint(f"  [dim]{e}[/dim]")
        rprint("  [dim]Wait a minute and run the command again.[/dim]")
        raise typer.Exit(code=1)
    except TimeoutError as e:
        rprint("  [red]API request timed out.[/red]")
        rprint(f"  [dim]{e}[/dim]")
        rprint("  [dim]Run the command again to retry.[/dim]")
        raise typer.Exit(code=1)
    except (ContentTooLargeError, TruncatedResponseError) as e:
        rprint(f"  [red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    now = datetime.now()
    seconds_in_day = now.hour * 3600 + now.minute * 60 + now.second
    filename = f"{now.strftime('%Y-%m-%d')}-{seconds_in_day}-{book.slug}.md"
    book_dir = settings.books_dir / book.slug
    book_dir.mkdir(parents=True, exist_ok=True)
    output_path = book_dir / filename
    output_path.write_text(final_digest, encoding="utf-8")

    rprint(f"\n[green]Digest saved:[/green] {output_path}")


@ideas_app.command("video-prompts")
def video_prompts_cmd(
    book_slug: str = typer.Argument(help="Book slug"),
    count: int = typer.Option(3, "--count", "-n", help="Number of video prompts to generate", min=1),
) -> None:
    """Generate video background prompt suggestions for a book's quote posts."""
    settings = load_settings()
    api_key = settings.gemini_api_key
    if not api_key:
        rprint("[red]Error:[/red] gemini_api_key is not configured.")
        raise typer.Exit(code=1)

    with get_connection(settings.db_path) as conn:
        book = get_book(conn, book_slug)
        if book is None:
            rprint(f"[red]Error:[/red] book not found: {book_slug}")
            raise typer.Exit(code=1)

        tags = get_tags_with_counts(conn, book.id)
        if not tags:
            rprint(f"No tags found for [bold]{book.title}[/bold].")
            rprint("[dim]Ideas need to be captioned first (anne ideas caption).[/dim]")
            raise typer.Exit(code=1)

        sample_quotes = get_sample_quotes_by_tag(conn, book.id)

    rprint(f"Generating {count} video prompts for [bold]{book.title}[/bold]...")

    try:
        results = generate_video_prompts(
            api_key=api_key,
            book_title=book.title,
            book_author=book.author,
            tags_with_counts=tags,
            sample_quotes=sample_quotes,
            count=count,
            min_interval=settings.llm_call_interval,
        )
    except RateLimitError as e:
        rprint("[red]Rate limited by Gemini API.[/red]")
        if str(e):
            rprint(f"[dim]{e}[/dim]")
        rprint("[dim]Wait a minute and run the command again.[/dim]")
        raise typer.Exit(code=1)
    except TimeoutError as e:
        rprint("[red]API request timed out.[/red]")
        rprint(f"[dim]{e}[/dim]")
        rprint("[dim]Run the command again to retry.[/dim]")
        raise typer.Exit(code=1)
    except (ContentTooLargeError, TruncatedResponseError) as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    if len(results) < count:
        rprint(f"[yellow]Warning:[/yellow] requested {count} prompts but got {len(results)}.")

    rprint(f"\n[bold]Video prompts for \"{escape(book.title)}\" by {escape(book.author)}[/bold]\n")
    for i, result in enumerate(results, 1):
        rprint(f"[bold]{i}.[/bold] {escape(result.prompt)}")
        if result.matching_tags:
            tags_str = ", ".join(result.matching_tags)
            rprint(f"   [dim]Tags: {escape(tags_str)}[/dim]")
        rprint()
