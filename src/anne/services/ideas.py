import json
import sqlite3

from anne.models import Idea, IdeaStatus, Source
from anne.services.parsers import ParsedIdea


def is_source_parsed(conn: sqlite3.Connection, source_id: int) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM ideas WHERE source_id = ?", (source_id,)
    ).fetchone()
    return row[0] > 0


def get_unparsed_sources(conn: sqlite3.Connection, book_id: int) -> list[Source]:
    rows = conn.execute(
        """SELECT s.* FROM sources s
           WHERE s.book_id = ?
           AND NOT EXISTS (SELECT 1 FROM ideas i WHERE i.source_id = s.id)
           ORDER BY s.imported_at""",
        (book_id,),
    ).fetchall()
    return [Source(**dict(r)) for r in rows]


def insert_ideas(
    conn: sqlite3.Connection,
    book_id: int,
    source_id: int,
    parsed_ideas: list[ParsedIdea],
) -> list[Idea]:
    results: list[Idea] = []
    for pi in parsed_ideas:
        conn.execute(
            """INSERT INTO ideas (book_id, source_id, status, raw_quote, raw_note, raw_ref)
               VALUES (?, ?, 'parsed', ?, ?, ?)""",
            (book_id, source_id, pi.raw_quote, pi.raw_note, pi.raw_ref),
        )
        row = conn.execute(
            "SELECT * FROM ideas WHERE id = last_insert_rowid()"
        ).fetchone()
        results.append(Idea(**dict(row)))
    return results


def list_ideas(conn: sqlite3.Connection, book_id: int) -> list[Idea]:
    rows = conn.execute(
        "SELECT * FROM ideas WHERE book_id = ? ORDER BY id", (book_id,)
    ).fetchall()
    return [Idea(**dict(r)) for r in rows]


def get_ideas_by_status(
    conn: sqlite3.Connection, book_id: int, status: IdeaStatus
) -> list[Idea]:
    rows = conn.execute(
        "SELECT * FROM ideas WHERE book_id = ? AND status = ? ORDER BY id",
        (book_id, status),
    ).fetchall()
    return [Idea(**dict(r)) for r in rows]


def triage_approve_idea(conn: sqlite3.Connection, idea_id: int) -> Idea:
    cursor = conn.execute(
        "UPDATE ideas SET status = ?, updated_at = datetime('now') WHERE id = ? AND status = ?",
        (IdeaStatus.triaged, idea_id, IdeaStatus.parsed),
    )
    if cursor.rowcount == 0:
        raise ValueError(f"Idea not found or not in parsed status: {idea_id}")
    row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
    return Idea(**dict(row))


def review_idea(
    conn: sqlite3.Connection,
    idea_id: int,
    reviewed_quote: str,
    reviewed_quote_emphasis: str | None,
    reviewed_comment: str,
) -> Idea:
    cursor = conn.execute(
        """UPDATE ideas SET status = ?, reviewed_quote = ?, reviewed_quote_emphasis = ?,
           reviewed_comment = ?, updated_at = datetime('now')
           WHERE id = ? AND status = ?""",
        (
            IdeaStatus.reviewed,
            reviewed_quote,
            reviewed_quote_emphasis,
            reviewed_comment,
            idea_id,
            IdeaStatus.triaged,
        ),
    )
    if cursor.rowcount == 0:
        raise ValueError(f"Idea not found or not in triaged status: {idea_id}")
    row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
    return Idea(**dict(row))


def caption_idea(
    conn: sqlite3.Connection,
    idea_id: int,
    presentation_text: str,
    tags: str,
) -> Idea:
    try:
        parsed = json.loads(tags)
        if not isinstance(parsed, list):
            raise ValueError("tags must be a JSON array")
    except json.JSONDecodeError as e:
        raise ValueError(f"tags must be valid JSON: {e}") from e
    cursor = conn.execute(
        """UPDATE ideas SET status = ?, presentation_text = ?, tags = ?,
           updated_at = datetime('now')
           WHERE id = ? AND status = ?""",
        (
            IdeaStatus.ready,
            presentation_text,
            tags,
            idea_id,
            IdeaStatus.reviewed,
        ),
    )
    if cursor.rowcount == 0:
        raise ValueError(f"Idea not found or not in reviewed status: {idea_id}")
    row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
    return Idea(**dict(row))


def reject_idea(
    conn: sqlite3.Connection, idea_id: int, rejection_reason: str | None
) -> Idea:
    cursor = conn.execute(
        "UPDATE ideas SET status = ?, rejection_reason = ?, updated_at = datetime('now') WHERE id = ? AND status = ?",
        (IdeaStatus.rejected, rejection_reason, idea_id, IdeaStatus.parsed),
    )
    if cursor.rowcount == 0:
        raise ValueError(f"Idea not found or not in parsed status: {idea_id}")
    row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
    return Idea(**dict(row))
