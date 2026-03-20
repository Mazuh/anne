import json
import sqlite3

from anne.models import Idea, IdeaStatus
from anne.services.ideas import (
    caption_idea,
    get_idea,
    get_ideas_by_status,
    reject_idea,
    review_idea,
    triage_approve_idea,
)
from anne.services.llm import (
    ContentTooLargeError,
    RateLimitError,
    caption_ideas_with_llm,
    review_ideas_with_llm,
    triage_ideas_with_llm,
)


def triage_book_ideas(
    conn: sqlite3.Connection,
    *,
    api_key: str,
    book_title: str,
    book_author: str,
    ideas: list[Idea],
    chunk_size: int,
    max_input_tokens: int,
    llm_call_interval: int,
) -> int:
    """Triage a list of parsed ideas in chunks. Returns total processed count."""
    total = 0
    chunks = [ideas[i : i + chunk_size] for i in range(0, len(ideas), chunk_size)]
    for chunk in chunks:
        decisions = triage_ideas_with_llm(
            api_key=api_key,
            book_title=book_title,
            book_author=book_author,
            ideas=chunk,
            total_ideas=len(ideas),
            max_input_tokens=max_input_tokens,
            min_interval=llm_call_interval,
        )
        for d in decisions:
            if d.decision == "triage":
                triage_approve_idea(conn, d.idea_id)
            elif d.decision == "reject":
                reject_idea(conn, d.idea_id, d.rejection_reason)
            total += 1
        conn.commit()
    return total


def review_book_ideas(
    conn: sqlite3.Connection,
    *,
    api_key: str,
    book_title: str,
    book_author: str,
    ideas: list[Idea],
    chunk_size: int,
    max_input_tokens: int,
    llm_call_interval: int,
    content_language: str,
    quote_target_length: int,
) -> int:
    """Review a list of triaged ideas in chunks. Returns total processed count."""
    total = 0
    chunks = [ideas[i : i + chunk_size] for i in range(0, len(ideas), chunk_size)]
    for chunk in chunks:
        results = review_ideas_with_llm(
            api_key=api_key,
            book_title=book_title,
            book_author=book_author,
            ideas=chunk,
            content_language=content_language,
            quote_target_length=quote_target_length,
            max_input_tokens=max_input_tokens,
            min_interval=llm_call_interval,
        )
        for r in results:
            review_idea(conn, r.idea_id, r.reviewed_quote, r.reviewed_quote_emphasis, r.reviewed_comment)
            total += 1
        conn.commit()
    return total


def caption_book_ideas(
    conn: sqlite3.Connection,
    *,
    api_key: str,
    book_title: str,
    book_author: str,
    ideas: list[Idea],
    chunk_size: int,
    max_input_tokens: int,
    llm_call_interval: int,
    content_language: str,
    cta_link: str,
) -> int:
    """Caption a list of reviewed ideas in chunks. Returns total processed count."""
    total = 0
    chunks = [ideas[i : i + chunk_size] for i in range(0, len(ideas), chunk_size)]
    for chunk in chunks:
        results = caption_ideas_with_llm(
            api_key=api_key,
            book_title=book_title,
            book_author=book_author,
            ideas=chunk,
            content_language=content_language,
            cta_link=cta_link,
            max_input_tokens=max_input_tokens,
            min_interval=llm_call_interval,
        )
        for r in results:
            caption_idea(conn, r.idea_id, r.presentation_text, json.dumps(r.tags, ensure_ascii=False))
            total += 1
        conn.commit()
    return total


def triage_single_idea(
    conn: sqlite3.Connection,
    *,
    api_key: str,
    book_title: str,
    book_author: str,
    idea_id: int,
    max_input_tokens: int,
    llm_call_interval: int,
) -> str:
    """Triage a single idea by ID. Returns 'triaged' or 'rejected'. Raises ValueError on invalid status."""
    idea = get_idea(conn, idea_id)
    if not idea or idea.status != IdeaStatus.parsed:
        raise ValueError(f"Idea {idea_id} is no longer in parsed status.")
    triage_book_ideas(
        conn,
        api_key=api_key,
        book_title=book_title,
        book_author=book_author,
        ideas=[idea],
        chunk_size=1,
        max_input_tokens=max_input_tokens,
        llm_call_interval=llm_call_interval,
    )
    updated = get_idea(conn, idea_id)
    if updated and updated.status == IdeaStatus.rejected:
        return "rejected"
    return "triaged"


def review_single_idea(
    conn: sqlite3.Connection,
    *,
    api_key: str,
    book_title: str,
    book_author: str,
    idea_id: int,
    max_input_tokens: int,
    llm_call_interval: int,
    content_language: str,
    quote_target_length: int,
) -> None:
    """Review a single idea by ID. Raises ValueError on invalid status."""
    idea = get_idea(conn, idea_id)
    if not idea or idea.status != IdeaStatus.triaged:
        raise ValueError(f"Idea {idea_id} is no longer in triaged status.")
    review_book_ideas(
        conn,
        api_key=api_key,
        book_title=book_title,
        book_author=book_author,
        ideas=[idea],
        chunk_size=1,
        max_input_tokens=max_input_tokens,
        llm_call_interval=llm_call_interval,
        content_language=content_language,
        quote_target_length=quote_target_length,
    )


def caption_single_idea(
    conn: sqlite3.Connection,
    *,
    api_key: str,
    book_title: str,
    book_author: str,
    idea_id: int,
    max_input_tokens: int,
    llm_call_interval: int,
    content_language: str,
    cta_link: str,
) -> None:
    """Caption a single idea by ID. Raises ValueError on invalid status."""
    idea = get_idea(conn, idea_id)
    if not idea or idea.status != IdeaStatus.reviewed:
        raise ValueError(f"Idea {idea_id} is no longer in reviewed status.")
    caption_book_ideas(
        conn,
        api_key=api_key,
        book_title=book_title,
        book_author=book_author,
        ideas=[idea],
        chunk_size=1,
        max_input_tokens=max_input_tokens,
        llm_call_interval=llm_call_interval,
        content_language=content_language,
        cta_link=cta_link,
    )


def format_llm_error(e: Exception) -> str:
    """Format LLM-related exceptions into user-friendly messages."""
    if isinstance(e, RateLimitError):
        return "Rate limited by Gemini API. Wait and retry."
    elif isinstance(e, ContentTooLargeError):
        return str(e)
    elif isinstance(e, ValueError):
        return str(e)
    return f"Error: {e}"
