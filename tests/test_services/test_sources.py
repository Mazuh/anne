import sqlite3
from pathlib import Path

from anne.models import SourceType
from anne.services.books import create_book
from anne.services.sources import (
    compute_fingerprint,
    detect_duplicate,
    detect_source_type,
    fetch_url,
    import_source,
    is_url,
    list_sources,
)


def test_compute_fingerprint(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    fp = compute_fingerprint(f)
    assert len(fp) == 64
    # Same content produces same fingerprint
    f2 = tmp_path / "test2.txt"
    f2.write_text("hello world")
    assert compute_fingerprint(f2) == fp


def test_detect_source_type():
    assert detect_source_type(Path("file.html")) == SourceType.kindle_export_html
    assert detect_source_type(Path("file.txt")) == SourceType.my_clippings_txt
    assert detect_source_type(Path("file.md")) == SourceType.essay_md
    assert detect_source_type(Path("file.xyz")) == SourceType.manual_notes


def test_import_source(tmp_db: sqlite3.Connection):
    book = create_book(tmp_db, "Test", "Author")
    source = import_source(
        tmp_db, book.id, SourceType.essay_md,
        "sources/essays/test.md", "abc123",
    )
    assert source.id is not None
    assert source.book_id == book.id
    assert source.type == SourceType.essay_md


def test_detect_duplicate(tmp_db: sqlite3.Connection):
    book = create_book(tmp_db, "Test", "Author")
    assert not detect_duplicate(tmp_db, book.id, "abc123")
    import_source(tmp_db, book.id, SourceType.essay_md, "test.md", "abc123")
    assert detect_duplicate(tmp_db, book.id, "abc123")


def test_is_url():
    assert is_url("https://example.com/page")
    assert is_url("http://example.com")
    assert not is_url("/some/file.txt")
    assert not is_url("relative/path.html")


def test_fetch_url(tmp_path: Path):
    from unittest.mock import patch, MagicMock

    html_content = b"<html><body>Hello</body></html>"
    mock_resp = MagicMock()
    mock_resp.read.return_value = html_content
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("anne.services.sources.urllib.request.urlopen", return_value=mock_resp):
        result = fetch_url("https://example.com/p/my-essay", tmp_path)

    assert result.exists()
    assert result.name == "example-com--p-my-essay.html"
    assert result.read_bytes() == html_content


def test_list_sources(tmp_db: sqlite3.Connection):
    book = create_book(tmp_db, "Test", "Author")
    import_source(tmp_db, book.id, SourceType.essay_md, "a.md", "fp1")
    import_source(tmp_db, book.id, SourceType.essay_txt, "b.txt", "fp2")
    sources = list_sources(tmp_db, book.id)
    assert len(sources) == 2
