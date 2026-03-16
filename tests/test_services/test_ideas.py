import sqlite3

from anne.services.books import create_book
from anne.services.ideas import (
    get_unparsed_sources,
    insert_ideas,
    is_source_parsed,
    list_ideas,
)
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
