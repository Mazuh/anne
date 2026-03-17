import json
import sqlite3

import pytest

from anne.models import IdeaStatus, SourceType
from anne.services.books import create_book
from anne.services.ideas import (
    count_ideas,
    get_idea,
    insert_ideas,
    list_ideas_paginated,
    triage_approve_idea,
    review_idea,
    update_idea,
)
from anne.services.parsers import ParsedIdea
from anne.services.sources import import_source


def _add_book_and_source(conn: sqlite3.Connection):
    book = create_book(conn, "Test Book", "Author")
    source = import_source(conn, book.id, SourceType.kindle_export_html, "sources/test.html", "fp1")
    return book, source


def _seed_ideas(conn: sqlite3.Connection, count: int = 5):
    book, source = _add_book_and_source(conn)
    parsed = [ParsedIdea(raw_quote=f"Quote {i}", raw_ref=f"Ch.{i}") for i in range(1, count + 1)]
    ideas = insert_ideas(conn, book.id, source.id, parsed)
    return book, source, ideas


# --- get_idea ---


def test_get_idea_found(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 1)
    idea = get_idea(tmp_db, ideas[0].id)
    assert idea is not None
    assert idea.raw_quote == "Quote 1"


def test_get_idea_not_found(tmp_db: sqlite3.Connection):
    assert get_idea(tmp_db, 9999) is None


# --- count_ideas ---


def test_count_ideas_all(tmp_db: sqlite3.Connection):
    _seed_ideas(tmp_db, 3)
    assert count_ideas(tmp_db) == 3


def test_count_ideas_by_book(tmp_db: sqlite3.Connection):
    book, source, _ = _seed_ideas(tmp_db, 3)
    assert count_ideas(tmp_db, book_id=book.id) == 3
    assert count_ideas(tmp_db, book_id=9999) == 0


def test_count_ideas_by_status(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 3)
    triage_approve_idea(tmp_db, ideas[0].id)
    assert count_ideas(tmp_db, status=IdeaStatus.parsed) == 2
    assert count_ideas(tmp_db, status=IdeaStatus.triaged) == 1


def test_count_ideas_by_book_and_status(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 3)
    triage_approve_idea(tmp_db, ideas[0].id)
    assert count_ideas(tmp_db, book_id=book.id, status=IdeaStatus.triaged) == 1


# --- list_ideas_paginated ---


def test_list_ideas_paginated_default(tmp_db: sqlite3.Connection):
    _seed_ideas(tmp_db, 5)
    ideas = list_ideas_paginated(tmp_db)
    assert len(ideas) == 5


def test_list_ideas_paginated_with_limit(tmp_db: sqlite3.Connection):
    _seed_ideas(tmp_db, 5)
    page1 = list_ideas_paginated(tmp_db, page=1, per_page=2)
    page2 = list_ideas_paginated(tmp_db, page=2, per_page=2)
    page3 = list_ideas_paginated(tmp_db, page=3, per_page=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    # No overlap
    ids = [i.id for i in page1 + page2 + page3]
    assert len(set(ids)) == 5


def test_list_ideas_paginated_filter_status(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 3)
    triage_approve_idea(tmp_db, ideas[0].id)
    result = list_ideas_paginated(tmp_db, status=IdeaStatus.triaged)
    assert len(result) == 1
    assert result[0].id == ideas[0].id


def test_list_ideas_paginated_filter_book(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 3)
    result = list_ideas_paginated(tmp_db, book_id=book.id)
    assert len(result) == 3
    result = list_ideas_paginated(tmp_db, book_id=9999)
    assert len(result) == 0


def test_list_ideas_paginated_empty_page(tmp_db: sqlite3.Connection):
    _seed_ideas(tmp_db, 2)
    result = list_ideas_paginated(tmp_db, page=5, per_page=25)
    assert result == []


# --- update_idea ---


def test_update_idea_raw_quote(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 1)
    updated = update_idea(tmp_db, ideas[0].id, raw_quote="New quote")
    assert updated.raw_quote == "New quote"


def test_update_idea_status_valid_transition(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 1)
    updated = update_idea(tmp_db, ideas[0].id, status="triaged")
    assert updated.status == IdeaStatus.triaged


def test_update_idea_status_invalid_transition(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 1)
    with pytest.raises(ValueError, match="Invalid status transition"):
        update_idea(tmp_db, ideas[0].id, status="reviewed")


def test_update_idea_status_force(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 1)
    updated = update_idea(tmp_db, ideas[0].id, force=True, status="reviewed")
    assert updated.status == IdeaStatus.reviewed


def test_update_idea_not_found(tmp_db: sqlite3.Connection):
    with pytest.raises(ValueError, match="Idea not found"):
        update_idea(tmp_db, 9999, raw_quote="x")


def test_update_idea_invalid_field(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 1)
    with pytest.raises(ValueError, match="Invalid fields"):
        update_idea(tmp_db, ideas[0].id, nonexistent="x")


def test_update_idea_tags_valid(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 1)
    updated = update_idea(tmp_db, ideas[0].id, tags='["a", "b"]')
    assert updated.tags == '["a", "b"]'


def test_update_idea_tags_invalid_json(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 1)
    with pytest.raises(ValueError, match="tags must be"):
        update_idea(tmp_db, ideas[0].id, tags="not json")


def test_update_idea_tags_not_array(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 1)
    with pytest.raises(ValueError, match="tags must be a JSON array"):
        update_idea(tmp_db, ideas[0].id, tags='{"a": 1}')


def test_update_idea_multiple_fields(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 1)
    updated = update_idea(tmp_db, ideas[0].id, raw_quote="New", raw_note="Note")
    assert updated.raw_quote == "New"
    assert updated.raw_note == "Note"


def test_update_idea_reject_transition(tmp_db: sqlite3.Connection):
    book, source, ideas = _seed_ideas(tmp_db, 1)
    updated = update_idea(tmp_db, ideas[0].id, status="rejected", rejection_reason="bad")
    assert updated.status == IdeaStatus.rejected
    assert updated.rejection_reason == "bad"
