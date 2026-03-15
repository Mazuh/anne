import sqlite3

from anne.models import Book
from anne.utils.exceptions import AnneError
from anne.utils.text import slugify


class DuplicateBookError(AnneError):
    pass


def create_book(conn: sqlite3.Connection, title: str, author: str) -> Book:
    slug = slugify(title)
    try:
        conn.execute(
            "INSERT INTO books (slug, title, author) VALUES (?, ?, ?)",
            (slug, title, author),
        )
    except sqlite3.IntegrityError:
        raise DuplicateBookError(f"A book with slug '{slug}' already exists.")
    row = conn.execute(
        "SELECT * FROM books WHERE slug = ?", (slug,)
    ).fetchone()
    return Book(**dict(row))


def list_books(conn: sqlite3.Connection) -> list[Book]:
    rows = conn.execute("SELECT * FROM books ORDER BY created_at DESC").fetchall()
    return [Book(**dict(r)) for r in rows]


def get_book(conn: sqlite3.Connection, slug: str) -> Book | None:
    row = conn.execute("SELECT * FROM books WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        return None
    return Book(**dict(row))


def get_book_stats(conn: sqlite3.Connection, book_id: int) -> dict:
    source_count = conn.execute(
        "SELECT COUNT(*) FROM sources WHERE book_id = ?", (book_id,)
    ).fetchone()[0]

    idea_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM ideas WHERE book_id = ? GROUP BY status",
        (book_id,),
    ).fetchall()
    idea_counts = {row["status"]: row["cnt"] for row in idea_rows}

    post_rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM posts WHERE book_id = ? GROUP BY status",
        (book_id,),
    ).fetchall()
    post_counts = {row["status"]: row["cnt"] for row in post_rows}

    asset_count = conn.execute(
        "SELECT COUNT(*) FROM assets WHERE book_id = ?", (book_id,)
    ).fetchone()[0]

    return {
        "sources": source_count,
        "ideas": idea_counts,
        "ideas_total": sum(idea_counts.values()),
        "posts": post_counts,
        "posts_total": sum(post_counts.values()),
        "assets": asset_count,
    }
