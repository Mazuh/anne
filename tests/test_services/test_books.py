import sqlite3

import pytest

from anne.services.books import create_book, list_books, get_book, get_book_stats, DuplicateBookError
from anne.utils.text import slugify


def test_slugify():
    assert slugify("O Príncipe") == "o-principe"
    assert slugify("Hello World!") == "hello-world"
    assert slugify("  Foo--Bar  ") == "foo-bar"


def test_create_book(tmp_db: sqlite3.Connection):
    book = create_book(tmp_db, "O Príncipe", "Maquiavel")
    assert book.slug == "o-principe"
    assert book.title == "O Príncipe"
    assert book.author == "Maquiavel"
    assert book.id is not None


def test_create_book_duplicate_slug(tmp_db: sqlite3.Connection):
    create_book(tmp_db, "Test Book", "Author")
    with pytest.raises(DuplicateBookError):
        create_book(tmp_db, "Test Book", "Other Author")


def test_list_books(tmp_db: sqlite3.Connection):
    create_book(tmp_db, "Book A", "Author A")
    create_book(tmp_db, "Book B", "Author B")
    books = list_books(tmp_db)
    assert len(books) == 2


def test_get_book(tmp_db: sqlite3.Connection):
    create_book(tmp_db, "My Book", "Author")
    book = get_book(tmp_db, "my-book")
    assert book is not None
    assert book.title == "My Book"


def test_get_book_not_found(tmp_db: sqlite3.Connection):
    book = get_book(tmp_db, "nonexistent")
    assert book is None


def test_get_book_stats(tmp_db: sqlite3.Connection):
    book = create_book(tmp_db, "Stats Book", "Author")
    stats = get_book_stats(tmp_db, book.id)
    assert stats["sources"] == 0
    assert stats["ideas_total"] == 0
    assert stats["posts_total"] == 0
    assert stats["assets"] == 0
