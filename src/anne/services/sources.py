import hashlib
import sqlite3
from pathlib import Path

from anne.models import Source, SourceType


EXTENSION_TYPE_MAP: dict[str, SourceType] = {
    ".html": SourceType.kindle_export_html,
    ".txt": SourceType.my_clippings_txt,
    ".md": SourceType.essay_md,
}


def compute_fingerprint(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def detect_duplicate(conn: sqlite3.Connection, book_id: int, fingerprint: str) -> bool:
    row = conn.execute(
        "SELECT id FROM sources WHERE book_id = ? AND fingerprint = ?",
        (book_id, fingerprint),
    ).fetchone()
    return row is not None


def detect_source_type(file_path: Path) -> SourceType:
    ext = file_path.suffix.lower()
    if ext in EXTENSION_TYPE_MAP:
        return EXTENSION_TYPE_MAP[ext]
    return SourceType.manual_notes


def import_source(
    conn: sqlite3.Connection,
    book_id: int,
    source_type: SourceType,
    relative_path: str,
    fingerprint: str,
) -> Source:
    conn.execute(
        "INSERT INTO sources (book_id, type, path, fingerprint) VALUES (?, ?, ?, ?)",
        (book_id, source_type.value, relative_path, fingerprint),
    )
    row = conn.execute(
        "SELECT * FROM sources WHERE book_id = ? AND fingerprint = ?",
        (book_id, fingerprint),
    ).fetchone()
    return Source(**dict(row))


def list_sources(conn: sqlite3.Connection, book_id: int) -> list[Source]:
    rows = conn.execute(
        "SELECT * FROM sources WHERE book_id = ? ORDER BY imported_at DESC",
        (book_id,),
    ).fetchall()
    return [Source(**dict(r)) for r in rows]
