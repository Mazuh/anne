import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from anne.cli.app import app
from anne.config.settings import Settings
from anne.db.connection import get_connection
from anne.db.migrate import apply_schema
from anne.models import SourceType
from anne.services.books import create_book
from anne.services.sources import import_source
import anne.services.llm as llm_module


@pytest.fixture(autouse=True)
def _reset_throttle():
    llm_module._last_call_time = 0

runner = CliRunner()


def _setup_book_with_kindle_source(tmp_settings: Settings) -> None:
    """Create a book with a Kindle HTML source file on disk."""
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        book = create_book(conn, "Test Book", "Author")
        # Create source file on disk
        source_dir = tmp_settings.books_dir / book.slug / "sources" / "kindle"
        source_dir.mkdir(parents=True, exist_ok=True)
        source_file = source_dir / "notes.html"
        source_file.write_text("""
<html><body>
<div class="noteHeading">Highlight (yellow) - Page 10 > Location 120</div>
<div class="noteText">A great quote from the book.</div>
<div class="noteHeading">Note - Page 10 > Location 120</div>
<div class="noteText">My thought about it.</div>
</body></html>
""")
        import_source(conn, book.id, SourceType.kindle_export_html, "sources/kindle/notes.html", "fp1")


def _setup_book_with_essay_source(tmp_settings: Settings) -> None:
    """Create a book with an essay MD source file on disk."""
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        book = create_book(conn, "Essay Book", "Essayist")
        source_dir = tmp_settings.books_dir / book.slug / "sources" / "essays"
        source_dir.mkdir(parents=True, exist_ok=True)
        source_file = source_dir / "essay.md"
        source_file.write_text("Some essay about the book.")
        import_source(conn, book.id, SourceType.essay_md, "sources/essays/essay.md", "fp2")


def test_idea_parse_kindle(tmp_settings: Settings):
    _setup_book_with_kindle_source(tmp_settings)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["idea-parse", "test-book"])
    assert result.exit_code == 0
    assert "1 idea extracted" in result.output
    assert "Total: 1 ideas parsed" in result.output


def test_idea_parse_idempotent(tmp_settings: Settings):
    _setup_book_with_kindle_source(tmp_settings)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        runner.invoke(app, ["idea-parse", "test-book"])
        result = runner.invoke(app, ["idea-parse", "test-book"])
    assert result.exit_code == 0
    assert "no unparsed sources" in result.output
    assert "Total: 0 ideas parsed" in result.output


def test_idea_parse_book_not_found(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["idea-parse", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_idea_parse_missing_api_key_for_essay(tmp_settings: Settings):
    _setup_book_with_essay_source(tmp_settings)
    settings_no_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key=None)
    with patch("anne.cli.ideas.load_settings", return_value=settings_no_key):
        result = runner.invoke(app, ["idea-parse", "essay-book"])
    assert result.exit_code == 1
    assert "gemini_api_key" in result.output


def _mock_gemini_response(ideas: list[dict]) -> MagicMock:
    body = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(ideas)}]}}
        ]
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_idea_parse_essay_with_llm(tmp_settings: Settings):
    _setup_book_with_essay_source(tmp_settings)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")

    mock_resp = _mock_gemini_response([
        {"raw_quote": "A book quote", "raw_note": "Essayist comment", "raw_ref": "Ch 1"},
    ])

    with (
        patch("anne.cli.ideas.load_settings", return_value=settings_with_key),
        patch("anne.services.llm.urllib.request.urlopen", return_value=mock_resp),
    ):
        result = runner.invoke(app, ["idea-parse", "essay-book"])
    assert result.exit_code == 0
    assert "1 idea extracted" in result.output


def test_idea_parse_all_books(tmp_settings: Settings):
    _setup_book_with_kindle_source(tmp_settings)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["idea-parse"])
    assert result.exit_code == 0
    assert "1 idea extracted" in result.output
