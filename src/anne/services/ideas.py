import json
import sqlite3

from anne.models import Idea, IdeaStatus, STABLE_STATUSES, Source
from anne.services.parsers import ParsedIdea
from anne.services.sources import get_or_create_manual_source


def insert_manual_idea(
    conn: sqlite3.Connection,
    book_id: int,
    raw_quote: str | None = None,
    raw_note: str | None = None,
    raw_ref: str | None = None,
) -> Idea:
    if not (raw_quote and raw_quote.strip()) and not (raw_note and raw_note.strip()):
        raise ValueError("At least one of raw_quote or raw_note must be provided")

    source = get_or_create_manual_source(conn, book_id)
    conn.execute(
        """INSERT INTO ideas (book_id, source_id, status, raw_quote, raw_note, raw_ref)
           VALUES (?, ?, 'triaged', ?, ?, ?)""",
        (book_id, source.id, raw_quote, raw_note, raw_ref),
    )
    row = conn.execute(
        "SELECT * FROM ideas WHERE id = last_insert_rowid()"
    ).fetchone()
    return Idea(**dict(row))


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


def get_commented_ideas(conn: sqlite3.Connection, book_id: int) -> list[Idea]:
    """Get triaged+ ideas that have a non-empty raw_note (reader's own comments)."""
    rows = conn.execute(
        """SELECT * FROM ideas
           WHERE book_id = ?
           AND status IN (?, ?, ?, ?)
           AND raw_note IS NOT NULL
           AND TRIM(raw_note) != ''
           ORDER BY id""",
        (book_id, IdeaStatus.triaged, IdeaStatus.reviewed, IdeaStatus.ready, IdeaStatus.published),
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


def get_random_stable_idea(
    conn: sqlite3.Connection,
    book_id: int | None = None,
) -> Idea | None:
    """Pick a random idea in a stable status (reviewed, ready, published)."""
    placeholders = ", ".join("?" for _ in STABLE_STATUSES)
    params: list[object] = [s.value for s in STABLE_STATUSES]
    query = f"SELECT * FROM ideas WHERE status IN ({placeholders})"
    if book_id is not None:
        query += " AND book_id = ?"
        params.append(book_id)
    query += " ORDER BY RANDOM() LIMIT 1"
    row = conn.execute(query, params).fetchone()
    if row is None:
        return None
    return Idea(**dict(row))


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
    reviewed_comment: str,
    allow_reviewed: bool = False,
) -> Idea:
    if allow_reviewed:
        cursor = conn.execute(
            """UPDATE ideas SET status = ?, reviewed_quote = ?,
               reviewed_comment = ?, updated_at = datetime('now')
               WHERE id = ? AND status IN (?, ?)""",
            (
                IdeaStatus.reviewed,
                reviewed_quote,
                reviewed_comment,
                idea_id,
                IdeaStatus.triaged,
                IdeaStatus.reviewed,
            ),
        )
    else:
        cursor = conn.execute(
            """UPDATE ideas SET status = ?, reviewed_quote = ?,
               reviewed_comment = ?, updated_at = datetime('now')
               WHERE id = ? AND status = ?""",
            (
                IdeaStatus.reviewed,
                reviewed_quote,
                reviewed_comment,
                idea_id,
                IdeaStatus.triaged,
            ),
        )
    if cursor.rowcount == 0:
        raise ValueError(f"Idea not found or not in expected status: {idea_id}")
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


def publish_idea(conn: sqlite3.Connection, idea_id: int) -> Idea:
    idea = get_idea(conn, idea_id)
    if idea is None:
        raise ValueError(f"Idea not found: {idea_id}")
    updated = update_idea(conn, idea_id, status=IdeaStatus.published)
    conn.execute(
        "UPDATE ideas SET published_at = datetime('now') WHERE id = ?",
        (idea_id,),
    )
    row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
    return Idea(**dict(row))


def queue_idea(conn: sqlite3.Connection, idea_id: int) -> Idea:
    idea = get_idea(conn, idea_id)
    if idea is None:
        raise ValueError(f"Idea not found: {idea_id}")
    return update_idea(conn, idea_id, status=IdeaStatus.queued)


def unqueue_idea(conn: sqlite3.Connection, idea_id: int) -> Idea:
    idea = get_idea(conn, idea_id)
    if idea is None:
        raise ValueError(f"Idea not found: {idea_id}")
    return update_idea(conn, idea_id, status=IdeaStatus.ready)


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


def get_idea(conn: sqlite3.Connection, idea_id: int) -> Idea | None:
    row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
    if row is None:
        return None
    return Idea(**dict(row))


def _apply_tag_condition(
    conditions: list[str], params: list[object], tag: str | None
) -> None:
    if tag is not None:
        conditions.append(
            "EXISTS (SELECT 1 FROM json_each(ideas.tags) AS j WHERE j.value = ?)"
        )
        params.append(tag)


def _apply_search_conditions(
    conditions: list[str], params: list[object], search: str | None
) -> None:
    if not search:
        return
    words = search.split()[:10]
    if not words:
        return
    fields = [
        "raw_quote",
        "raw_note",
        "reviewed_quote",
        "reviewed_comment",
        "presentation_text",
    ]
    # Each word must match at least one field (AND across words, OR across fields).
    for word in words:
        escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        or_clause = " OR ".join(f"{f} LIKE ? ESCAPE '\\'" for f in fields)
        conditions.append(f"({or_clause})")
        params.extend([pattern] * len(fields))


def get_distinct_tags(conn: sqlite3.Connection, book_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT j.value FROM ideas, json_each(ideas.tags) AS j "
        "WHERE ideas.book_id = ? AND ideas.tags IS NOT NULL AND ideas.tags != '' "
        "ORDER BY j.value",
        (book_id,),
    ).fetchall()
    return [row[0] for row in rows]


def get_tags_with_counts(
    conn: sqlite3.Connection, book_id: int | None = None
) -> list[tuple[str, int]]:
    query = (
        "SELECT j.value, COUNT(*) AS cnt "
        "FROM ideas, json_each(ideas.tags) AS j "
        "WHERE ideas.tags IS NOT NULL AND ideas.tags != ''"
    )
    params: list[object] = []
    if book_id is not None:
        query += " AND ideas.book_id = ?"
        params.append(book_id)
    query += " GROUP BY j.value ORDER BY cnt DESC, j.value"
    rows = conn.execute(query, params).fetchall()
    return [(row[0], row[1]) for row in rows]


def get_sample_quotes_by_tag(
    conn: sqlite3.Connection,
    book_id: int,
    samples_per_tag: int = 2,
) -> dict[str, list[str]]:
    """Return a dict mapping each tag to a few sample reviewed_quote strings."""
    rows = conn.execute(
        "SELECT j.value AS tag, ideas.reviewed_quote "
        "FROM ideas, json_each(ideas.tags) AS j "
        "WHERE ideas.book_id = ? "
        "AND ideas.tags IS NOT NULL AND ideas.tags != '' "
        "AND ideas.reviewed_quote IS NOT NULL "
        "ORDER BY j.value, ideas.id",
        (book_id,),
    ).fetchall()

    result: dict[str, list[str]] = {}
    for tag, quote in rows:
        if tag not in result:
            result[tag] = []
        if len(result[tag]) < samples_per_tag:
            result[tag].append(quote)
    return result


def count_ideas(
    conn: sqlite3.Connection,
    book_id: int | None = None,
    status: IdeaStatus | None = None,
    search: str | None = None,
    tag: str | None = None,
) -> int:
    query = "SELECT COUNT(*) FROM ideas"
    conditions: list[str] = []
    params: list[object] = []
    if book_id is not None:
        conditions.append("book_id = ?")
        params.append(book_id)
    if status is not None:
        conditions.append("status = ?")
        params.append(status.value)
    _apply_tag_condition(conditions, params, tag)
    _apply_search_conditions(conditions, params, search)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    row = conn.execute(query, params).fetchone()
    return row[0]


def list_ideas_paginated(
    conn: sqlite3.Connection,
    book_id: int | None = None,
    status: IdeaStatus | None = None,
    page: int = 1,
    per_page: int = 25,
    search: str | None = None,
    tag: str | None = None,
) -> list[Idea]:
    query = "SELECT * FROM ideas"
    conditions: list[str] = []
    params: list[object] = []
    if book_id is not None:
        conditions.append("book_id = ?")
        params.append(book_id)
    if status is not None:
        conditions.append("status = ?")
        params.append(status.value)
    _apply_tag_condition(conditions, params, tag)
    _apply_search_conditions(conditions, params, search)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id"
    offset = (page - 1) * per_page
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    rows = conn.execute(query, params).fetchall()
    return [Idea(**dict(r)) for r in rows]


# Valid forward transitions (without --force)
_VALID_TRANSITIONS: dict[IdeaStatus, set[IdeaStatus]] = {
    IdeaStatus.parsed: {IdeaStatus.triaged, IdeaStatus.rejected},
    IdeaStatus.rejected: {IdeaStatus.parsed},
    IdeaStatus.triaged: {IdeaStatus.reviewed, IdeaStatus.rejected},
    IdeaStatus.reviewed: {IdeaStatus.ready, IdeaStatus.rejected},
    IdeaStatus.ready: {IdeaStatus.published, IdeaStatus.queued, IdeaStatus.rejected},
    IdeaStatus.queued: {IdeaStatus.published, IdeaStatus.ready, IdeaStatus.rejected},
    IdeaStatus.published: set(),
}

# Fields allowed in update_idea
_UPDATABLE_FIELDS: set[str] = {
    "status",
    "raw_quote",
    "raw_note",
    "raw_ref",
    "reviewed_quote",
    "reviewed_comment",
    "presentation_text",
    "rejection_reason",
    "tags",
}


def update_idea(
    conn: sqlite3.Connection, idea_id: int, force: bool = False, **fields: object
) -> Idea:
    idea = get_idea(conn, idea_id)
    if idea is None:
        raise ValueError(f"Idea not found: {idea_id}")

    invalid = set(fields) - _UPDATABLE_FIELDS
    if invalid:
        raise ValueError(f"Invalid fields: {', '.join(sorted(invalid))}")

    if "status" in fields:
        new_status = IdeaStatus(str(fields["status"]))
        if not force:
            current = IdeaStatus(idea.status)
            allowed = _VALID_TRANSITIONS.get(current, set())
            if new_status not in allowed:
                raise ValueError(
                    f"Invalid status transition: {current} → {new_status} "
                    f"(allowed: {', '.join(sorted(s.value for s in allowed)) or 'none'}). "
                    f"Use --force to override."
                )

    if "tags" in fields:
        tags_val = fields["tags"]
        try:
            parsed = json.loads(str(tags_val))
            if not isinstance(parsed, list):
                raise ValueError("tags must be a JSON array")
        except json.JSONDecodeError as e:
            raise ValueError(f"tags must be valid JSON: {e}") from e

    set_clauses = []
    params: list[object] = []
    for field, value in fields.items():
        assert field in _UPDATABLE_FIELDS, f"unexpected field: {field}"
        set_clauses.append(f"{field} = ?")
        params.append(value)
    set_clauses.append("updated_at = datetime('now')")
    params.append(idea_id)

    conn.execute(
        f"UPDATE ideas SET {', '.join(set_clauses)} WHERE id = ?",
        params,
    )

    updated = get_idea(conn, idea_id)
    if updated is None:
        raise ValueError(f"Idea not found after update: {idea_id}")
    return updated
