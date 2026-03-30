import sqlite3

import pytest

from anne.services.books import create_book
from anne.services.ideas import (
    triage_approve_idea,
    caption_idea,
    count_ideas,
    get_distinct_tags,
    get_ideas_by_status,
    get_unparsed_sources,
    insert_ideas,
    is_source_parsed,
    list_ideas,
    list_ideas_paginated,
    publish_idea,
    queue_idea,
    reject_idea,
    review_idea,
)
from anne.models import IdeaStatus
from anne.services.parsers import ParsedIdea
from anne.services.sources import import_source
from anne.models import SourceType


def _add_book_and_source(conn: sqlite3.Connection, source_type: SourceType = SourceType.kindle_export_html):
    book = create_book(conn, "Test Book", "Author")
    source = import_source(conn, book.id, source_type, "sources/kindle/test.html", "fp1")
    return book, source


def test_insert_ideas_quote_only(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    parsed = [ParsedIdea(raw_quote="A quote")]
    ideas = insert_ideas(tmp_db, book.id, source.id, parsed)
    assert len(ideas) == 1
    assert ideas[0].raw_quote == "A quote"
    assert ideas[0].raw_note is None
    assert ideas[0].status == "parsed"


def test_insert_ideas_note_only(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    parsed = [ParsedIdea(raw_note="A thought")]
    ideas = insert_ideas(tmp_db, book.id, source.id, parsed)
    assert len(ideas) == 1
    assert ideas[0].raw_quote is None
    assert ideas[0].raw_note == "A thought"


def test_insert_ideas_both(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    parsed = [ParsedIdea(raw_quote="Quote", raw_note="Note", raw_ref="Page 5")]
    ideas = insert_ideas(tmp_db, book.id, source.id, parsed)
    assert len(ideas) == 1
    assert ideas[0].raw_quote == "Quote"
    assert ideas[0].raw_note == "Note"
    assert ideas[0].raw_ref == "Page 5"


def test_is_source_parsed(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    assert not is_source_parsed(tmp_db, source.id)
    insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q")])
    assert is_source_parsed(tmp_db, source.id)


def test_get_unparsed_sources(tmp_db: sqlite3.Connection):
    book = create_book(tmp_db, "Test Book", "Author")
    s1 = import_source(tmp_db, book.id, SourceType.kindle_export_html, "a.html", "fp1")
    s2 = import_source(tmp_db, book.id, SourceType.essay_md, "b.md", "fp2")

    unparsed = get_unparsed_sources(tmp_db, book.id)
    assert len(unparsed) == 2

    insert_ideas(tmp_db, book.id, s1.id, [ParsedIdea(raw_quote="Q")])
    unparsed = get_unparsed_sources(tmp_db, book.id)
    assert len(unparsed) == 1
    assert unparsed[0].id == s2.id


def test_list_ideas(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    insert_ideas(tmp_db, book.id, source.id, [
        ParsedIdea(raw_quote="Q1"),
        ParsedIdea(raw_note="N2"),
    ])
    ideas = list_ideas(tmp_db, book.id)
    assert len(ideas) == 2


def test_get_ideas_by_status(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    insert_ideas(tmp_db, book.id, source.id, [
        ParsedIdea(raw_quote="Q1"),
        ParsedIdea(raw_note="N2"),
    ])
    parsed = get_ideas_by_status(tmp_db, book.id, IdeaStatus.parsed)
    assert len(parsed) == 2
    triaged = get_ideas_by_status(tmp_db, book.id, IdeaStatus.triaged)
    assert len(triaged) == 0


def test_get_ideas_by_status_empty(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    result = get_ideas_by_status(tmp_db, book.id, IdeaStatus.parsed)
    assert result == []


def test_triage_approve_idea(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    original_updated = ideas[0].updated_at

    triaged = triage_approve_idea(tmp_db, ideas[0].id)
    assert triaged.status == IdeaStatus.triaged
    assert triaged.updated_at >= original_updated


def test_reject_idea(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])

    rejected = reject_idea(tmp_db, ideas[0].id, "just a vocab word")
    assert rejected.status == IdeaStatus.rejected
    assert rejected.rejection_reason == "just a vocab word"


def test_reject_idea_not_found(tmp_db: sqlite3.Connection):
    with pytest.raises(ValueError, match="Idea not found"):
        reject_idea(tmp_db, 9999, "reason")


def test_triage_approve_idea_not_found(tmp_db: sqlite3.Connection):
    with pytest.raises(ValueError, match="Idea not found"):
        triage_approve_idea(tmp_db, 9999)


def test_triage_approve_idea_already_rejected(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    reject_idea(tmp_db, ideas[0].id, "test")
    with pytest.raises(ValueError, match="not in parsed status"):
        triage_approve_idea(tmp_db, ideas[0].id)


def test_reject_idea_already_approved(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    triage_approve_idea(tmp_db, ideas[0].id)
    with pytest.raises(ValueError, match="not in parsed status"):
        reject_idea(tmp_db, ideas[0].id, "too late")


def test_review_idea(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Original quote", raw_note="A note")])
    triage_approve_idea(tmp_db, ideas[0].id)

    reviewed = review_idea(
        tmp_db, ideas[0].id,
        reviewed_quote="**Shortened** quote",
        reviewed_comment="Factual context about the author.",
    )
    assert reviewed.status == IdeaStatus.reviewed
    assert reviewed.reviewed_quote == "**Shortened** quote"
    assert reviewed.reviewed_comment == "Factual context about the author."
    # Raw fields must be untouched
    assert reviewed.raw_quote == "Original quote"
    assert reviewed.raw_note == "A note"


def test_review_idea_not_approved(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    # Still in 'parsed' status
    with pytest.raises(ValueError, match="not in expected status"):
        review_idea(tmp_db, ideas[0].id, "q", "c")


def test_review_idea_not_found(tmp_db: sqlite3.Connection):
    with pytest.raises(ValueError, match="not in expected status"):
        review_idea(tmp_db, 9999, "q", "c")


def test_review_idea_without_emphasis(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Plain quote")])
    triage_approve_idea(tmp_db, ideas[0].id)

    reviewed = review_idea(tmp_db, ideas[0].id, "Plain quote shortened", "Context.")
    assert reviewed.reviewed_quote == "Plain quote shortened"
    assert "**" not in reviewed.reviewed_quote


def test_review_idea_redo(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Original quote")])
    triage_approve_idea(tmp_db, ideas[0].id)
    review_idea(tmp_db, ideas[0].id, "First review", "First context.")
    assert ideas[0].id is not None

    # Without allow_reviewed, re-review should fail
    with pytest.raises(ValueError, match="not in expected status"):
        review_idea(tmp_db, ideas[0].id, "Second review", "Second context.")

    # With allow_reviewed, re-review should succeed
    re_reviewed = review_idea(
        tmp_db, ideas[0].id, "Second review", "Second context.", allow_reviewed=True,
    )
    assert re_reviewed.status == IdeaStatus.reviewed
    assert re_reviewed.reviewed_quote == "Second review"
    assert re_reviewed.reviewed_comment == "Second context."


def test_caption_idea(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Original quote")])
    triage_approve_idea(tmp_db, ideas[0].id)
    review_idea(tmp_db, ideas[0].id, "**Short** quote", "Context.")

    captioned = caption_idea(
        tmp_db, ideas[0].id,
        presentation_text="This is the Instagram caption.",
        tags='["poder", "ironia"]',
    )
    assert captioned.status == IdeaStatus.ready
    assert captioned.presentation_text == "This is the Instagram caption."
    assert captioned.tags == '["poder", "ironia"]'
    # Previous fields untouched
    assert captioned.reviewed_quote == "**Short** quote"
    assert captioned.raw_quote == "Original quote"


def test_caption_idea_not_reviewed(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    triage_approve_idea(tmp_db, ideas[0].id)
    # Still in 'triaged' status, not reviewed
    with pytest.raises(ValueError, match="not in reviewed status"):
        caption_idea(tmp_db, ideas[0].id, "caption", "[]")


def test_caption_idea_not_found(tmp_db: sqlite3.Connection):
    with pytest.raises(ValueError, match="not in reviewed status"):
        caption_idea(tmp_db, 9999, "caption", "[]")


def test_caption_idea_invalid_tags_json(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    triage_approve_idea(tmp_db, ideas[0].id)
    review_idea(tmp_db, ideas[0].id, "Q", "C")
    with pytest.raises(ValueError, match="tags must be valid JSON"):
        caption_idea(tmp_db, ideas[0].id, "caption", "not json")


def test_caption_idea_tags_not_array(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    triage_approve_idea(tmp_db, ideas[0].id)
    review_idea(tmp_db, ideas[0].id, "Q", "C")
    with pytest.raises(ValueError, match="tags must be a JSON array"):
        caption_idea(tmp_db, ideas[0].id, "caption", '{"not": "array"}')


def test_publish_idea(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    triage_approve_idea(tmp_db, ideas[0].id)
    review_idea(tmp_db, ideas[0].id, "Q1", "context")
    caption_idea(tmp_db, ideas[0].id, "caption", '["tag"]')
    published = publish_idea(tmp_db, ideas[0].id)
    assert published.status == IdeaStatus.published
    assert published.published_at is not None


def test_publish_idea_not_ready(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    triage_approve_idea(tmp_db, ideas[0].id)
    review_idea(tmp_db, ideas[0].id, "Q1", "context")
    with pytest.raises(ValueError, match="Invalid status transition"):
        publish_idea(tmp_db, ideas[0].id)


def test_queue_idea(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    triage_approve_idea(tmp_db, ideas[0].id)
    review_idea(tmp_db, ideas[0].id, "Q1", "context")
    caption_idea(tmp_db, ideas[0].id, "caption", '["tag"]')
    queued = queue_idea(tmp_db, ideas[0].id)
    assert queued.status == IdeaStatus.queued


def test_queue_idea_not_ready(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    triage_approve_idea(tmp_db, ideas[0].id)
    review_idea(tmp_db, ideas[0].id, "Q1", "context")
    with pytest.raises(ValueError, match="Invalid status transition"):
        queue_idea(tmp_db, ideas[0].id)


def test_publish_queued_idea(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    ideas = insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    triage_approve_idea(tmp_db, ideas[0].id)
    review_idea(tmp_db, ideas[0].id, "Q1", "context")
    caption_idea(tmp_db, ideas[0].id, "caption", '["tag"]')
    queue_idea(tmp_db, ideas[0].id)
    published = publish_idea(tmp_db, ideas[0].id)
    assert published.status == IdeaStatus.published
    assert published.published_at is not None


def _make_ready_idea(conn: sqlite3.Connection, book_id: int, source_id: int, quote: str, tags: str) -> None:
    """Helper to create an idea and advance it to ready status with tags."""
    ideas = insert_ideas(conn, book_id, source_id, [ParsedIdea(raw_quote=quote)])
    triage_approve_idea(conn, ideas[0].id)
    review_idea(conn, ideas[0].id, quote, "context")
    caption_idea(conn, ideas[0].id, "caption", tags)


def test_get_distinct_tags(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    _make_ready_idea(tmp_db, book.id, source.id, "Q1", '["philosophy", "ethics"]')
    _make_ready_idea(tmp_db, book.id, source.id, "Q2", '["philosophy", "power"]')

    tags = get_distinct_tags(tmp_db, book.id)
    assert tags == ["ethics", "philosophy", "power"]


def test_get_distinct_tags_empty(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q1")])
    tags = get_distinct_tags(tmp_db, book.id)
    assert tags == []


def test_count_ideas_with_tag_filter(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    _make_ready_idea(tmp_db, book.id, source.id, "Q1", '["philosophy", "ethics"]')
    _make_ready_idea(tmp_db, book.id, source.id, "Q2", '["philosophy", "power"]')
    _make_ready_idea(tmp_db, book.id, source.id, "Q3", '["irony"]')

    assert count_ideas(tmp_db, book_id=book.id, tag="philosophy") == 2
    assert count_ideas(tmp_db, book_id=book.id, tag="ethics") == 1
    assert count_ideas(tmp_db, book_id=book.id, tag="irony") == 1
    assert count_ideas(tmp_db, book_id=book.id, tag="nonexistent") == 0
    assert count_ideas(tmp_db, book_id=book.id) == 3


def test_list_ideas_paginated_with_tag_filter(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    _make_ready_idea(tmp_db, book.id, source.id, "Q1", '["philosophy", "ethics"]')
    _make_ready_idea(tmp_db, book.id, source.id, "Q2", '["philosophy", "power"]')
    _make_ready_idea(tmp_db, book.id, source.id, "Q3", '["irony"]')

    results = list_ideas_paginated(tmp_db, book_id=book.id, tag="philosophy")
    assert len(results) == 2
    quotes = {r.raw_quote for r in results}
    assert quotes == {"Q1", "Q2"}

    results = list_ideas_paginated(tmp_db, book_id=book.id, tag="irony")
    assert len(results) == 1
    assert results[0].raw_quote == "Q3"


def test_tag_filter_combined_with_status(tmp_db: sqlite3.Connection):
    book, source = _add_book_and_source(tmp_db)
    # One ready idea with "philosophy" tag
    _make_ready_idea(tmp_db, book.id, source.id, "Q1", '["philosophy"]')
    # One parsed idea (no tags)
    insert_ideas(tmp_db, book.id, source.id, [ParsedIdea(raw_quote="Q2")])

    # Filter by tag only — should find the ready one
    assert count_ideas(tmp_db, book_id=book.id, tag="philosophy") == 1
    # Filter by tag + status=ready — should still find it
    assert count_ideas(tmp_db, book_id=book.id, status=IdeaStatus.ready, tag="philosophy") == 1
    # Filter by tag + status=parsed — should find nothing
    assert count_ideas(tmp_db, book_id=book.id, status=IdeaStatus.parsed, tag="philosophy") == 0
