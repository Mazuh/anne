import hashlib
import sqlite3
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

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


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


MAX_FETCH_SIZE = 10 * 1024 * 1024  # 10 MB


def fetch_url(url: str, dest_dir: Path) -> Path:
    parsed = urlparse(url)
    # Build a filename from domain + path to avoid collisions
    domain = parsed.netloc.replace(".", "-")
    path_part = parsed.path.strip("/").replace("/", "-") or "index"
    filename = f"{domain}--{path_part}"
    if not filename.endswith(".html"):
        filename += ".html"
    dest = dest_dir / filename

    req = urllib.request.Request(url, headers={"User-Agent": "Anne/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read(MAX_FETCH_SIZE + 1)
        if len(data) > MAX_FETCH_SIZE:
            raise ValueError(f"Response too large (>{MAX_FETCH_SIZE} bytes)")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    return dest


def list_sources(conn: sqlite3.Connection, book_id: int) -> list[Source]:
    rows = conn.execute(
        "SELECT * FROM sources WHERE book_id = ? ORDER BY imported_at DESC",
        (book_id,),
    ).fetchall()
    return [Source(**dict(r)) for r in rows]
