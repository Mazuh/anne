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
from anne.services.ideas import insert_ideas, review_idea
from anne.services.sources import import_source
from anne.services.parsers import ParsedIdea
from anne.services.ideas import approve_idea
from anne.services.llm import RateLimitError
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


# --- idea-triage tests ---


def _setup_book_with_parsed_ideas(tmp_settings: Settings) -> None:
    """Create a book with parsed ideas in the DB."""
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        book = create_book(conn, "Test Book", "Author")
        source = import_source(
            conn, book.id, SourceType.kindle_export_html, "sources/kindle/notes.html", "fp1"
        )
        insert_ideas(conn, book.id, source.id, [
            ParsedIdea(raw_quote="A great insight about the world"),
            ParsedIdea(raw_note="ephemeral vocab word"),
            ParsedIdea(raw_quote="Another good idea", raw_note="With a note"),
        ])


def _mock_triage_response(decisions: list[dict]) -> MagicMock:
    body = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(decisions)}]}}
        ]
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_idea_triage_approves_and_rejects(tmp_settings: Settings):
    _setup_book_with_parsed_ideas(tmp_settings)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")

    # Get actual idea IDs from DB
    with get_connection(tmp_settings.db_path) as conn:
        rows = conn.execute("SELECT id FROM ideas ORDER BY id").fetchall()
    idea_ids = [r["id"] for r in rows]

    mock_resp = _mock_triage_response([
        {"id": idea_ids[0], "decision": "approve"},
        {"id": idea_ids[1], "decision": "reject", "rejection_reason": "vocab lookup"},
        {"id": idea_ids[2], "decision": "approve"},
    ])

    with (
        patch("anne.cli.ideas.load_settings", return_value=settings_with_key),
        patch("anne.services.llm.urllib.request.urlopen", return_value=mock_resp),
    ):
        result = runner.invoke(app, ["idea-triage", "test-book"])
    assert result.exit_code == 0
    assert "Approved" in result.output
    assert "Rejected" in result.output
    assert "vocab lookup" in result.output
    assert "2 approved, 1 rejected (3 ideas)" in result.output

    # Verify DB state
    with get_connection(tmp_settings.db_path) as conn:
        row = conn.execute("SELECT status FROM ideas WHERE id = ?", (idea_ids[0],)).fetchone()
        assert row["status"] == "approved"
        row = conn.execute("SELECT status, rejection_reason FROM ideas WHERE id = ?", (idea_ids[1],)).fetchone()
        assert row["status"] == "rejected"
        assert row["rejection_reason"] == "vocab lookup"


def test_idea_triage_no_parsed_ideas(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        create_book(conn, "Empty Book", "Author")
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")
    with patch("anne.cli.ideas.load_settings", return_value=settings_with_key):
        result = runner.invoke(app, ["idea-triage", "empty-book"])
    assert result.exit_code == 0
    assert "no parsed ideas" in result.output


def test_idea_triage_book_not_found(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")
    with patch("anne.cli.ideas.load_settings", return_value=settings_with_key):
        result = runner.invoke(app, ["idea-triage", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_idea_triage_missing_api_key(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    settings_no_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key=None)
    with patch("anne.cli.ideas.load_settings", return_value=settings_no_key):
        result = runner.invoke(app, ["idea-triage"])
    assert result.exit_code == 1
    assert "gemini_api_key" in result.output


def test_idea_triage_all_books(tmp_settings: Settings):
    _setup_book_with_parsed_ideas(tmp_settings)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")

    with get_connection(tmp_settings.db_path) as conn:
        rows = conn.execute("SELECT id FROM ideas ORDER BY id").fetchall()
    idea_ids = [r["id"] for r in rows]

    mock_resp = _mock_triage_response([
        {"id": idea_ids[0], "decision": "approve"},
        {"id": idea_ids[1], "decision": "approve"},
        {"id": idea_ids[2], "decision": "approve"},
    ])

    with (
        patch("anne.cli.ideas.load_settings", return_value=settings_with_key),
        patch("anne.services.llm.urllib.request.urlopen", return_value=mock_resp),
    ):
        result = runner.invoke(app, ["idea-triage"])
    assert result.exit_code == 0
    assert "3 approved, 0 rejected (3 ideas)" in result.output


def test_idea_triage_rate_limited(tmp_settings: Settings):
    _setup_book_with_parsed_ideas(tmp_settings)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")

    with (
        patch("anne.cli.ideas.load_settings", return_value=settings_with_key),
        patch("anne.cli.ideas.triage_ideas_with_llm", side_effect=RateLimitError("rate limited")),
    ):
        result = runner.invoke(app, ["idea-triage", "test-book"])
    assert result.exit_code == 1
    assert "Rate limited" in result.output
    assert "Progress so far has been saved" in result.output


# --- idea-review tests ---


def _setup_book_with_approved_ideas(tmp_settings: Settings) -> None:
    """Create a book with approved ideas in the DB."""
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        book = create_book(conn, "Test Book", "Author")
        source = import_source(
            conn, book.id, SourceType.kindle_export_html, "sources/kindle/notes.html", "fp1"
        )
        ideas = insert_ideas(conn, book.id, source.id, [
            ParsedIdea(raw_quote="A great insight about the world", raw_note="My thought"),
            ParsedIdea(raw_quote="Another good idea", raw_note="With a note"),
        ])
        for idea in ideas:
            approve_idea(conn, idea.id)


def _mock_review_response(results: list[dict]) -> MagicMock:
    body = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(results)}]}}
        ]
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_idea_review_happy_path(tmp_settings: Settings):
    _setup_book_with_approved_ideas(tmp_settings)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")

    with get_connection(tmp_settings.db_path) as conn:
        rows = conn.execute("SELECT id FROM ideas WHERE status = 'approved' ORDER BY id").fetchall()
    idea_ids = [r["id"] for r in rows]

    mock_resp = _mock_review_response([
        {
            "id": idea_ids[0],
            "reviewed_quote": "Great insight",
            "reviewed_quote_emphasis": "**Great** insight",
            "reviewed_comment": "The author reflects on society.",
        },
        {
            "id": idea_ids[1],
            "reviewed_quote": "Good idea",
            "reviewed_quote_emphasis": None,
            "reviewed_comment": "Historical context for this passage.",
        },
    ])

    with (
        patch("anne.cli.ideas.load_settings", return_value=settings_with_key),
        patch("anne.services.llm.urllib.request.urlopen", return_value=mock_resp),
    ):
        result = runner.invoke(app, ["idea-review", "test-book"])
    assert result.exit_code == 0
    assert "Reviewed" in result.output
    assert "2 ideas reviewed" in result.output

    # Verify DB state
    with get_connection(tmp_settings.db_path) as conn:
        row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_ids[0],)).fetchone()
        assert row["status"] == "reviewed"
        assert row["reviewed_quote"] == "Great insight"
        assert row["reviewed_quote_emphasis"] == "**Great** insight"
        assert row["reviewed_comment"] == "The author reflects on society."
        # Raw fields untouched
        assert row["raw_quote"] == "A great insight about the world"
        assert row["raw_note"] == "My thought"

        row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_ids[1],)).fetchone()
        assert row["status"] == "reviewed"
        assert row["reviewed_quote_emphasis"] is None


def test_idea_review_no_approved_ideas(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        create_book(conn, "Empty Book", "Author")
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")
    with patch("anne.cli.ideas.load_settings", return_value=settings_with_key):
        result = runner.invoke(app, ["idea-review", "empty-book"])
    assert result.exit_code == 0
    assert "no approved ideas" in result.output


def test_idea_review_book_not_found(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")
    with patch("anne.cli.ideas.load_settings", return_value=settings_with_key):
        result = runner.invoke(app, ["idea-review", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_idea_review_missing_api_key(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    settings_no_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key=None)
    with patch("anne.cli.ideas.load_settings", return_value=settings_no_key):
        result = runner.invoke(app, ["idea-review"])
    assert result.exit_code == 1
    assert "gemini_api_key" in result.output


def test_idea_review_all_books(tmp_settings: Settings):
    _setup_book_with_approved_ideas(tmp_settings)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")

    with get_connection(tmp_settings.db_path) as conn:
        rows = conn.execute("SELECT id FROM ideas WHERE status = 'approved' ORDER BY id").fetchall()
    idea_ids = [r["id"] for r in rows]

    mock_resp = _mock_review_response([
        {"id": idea_ids[0], "reviewed_quote": "Q1", "reviewed_quote_emphasis": None, "reviewed_comment": "C1"},
        {"id": idea_ids[1], "reviewed_quote": "Q2", "reviewed_quote_emphasis": None, "reviewed_comment": "C2"},
    ])

    with (
        patch("anne.cli.ideas.load_settings", return_value=settings_with_key),
        patch("anne.services.llm.urllib.request.urlopen", return_value=mock_resp),
    ):
        result = runner.invoke(app, ["idea-review"])
    assert result.exit_code == 0
    assert "2 ideas reviewed" in result.output


def test_idea_review_rate_limited(tmp_settings: Settings):
    _setup_book_with_approved_ideas(tmp_settings)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")

    with (
        patch("anne.cli.ideas.load_settings", return_value=settings_with_key),
        patch("anne.cli.ideas.review_ideas_with_llm", side_effect=RateLimitError("rate limited")),
    ):
        result = runner.invoke(app, ["idea-review", "test-book"])
    assert result.exit_code == 1
    assert "Rate limited" in result.output
    assert "Progress so far has been saved" in result.output


def test_idea_review_partial_response(tmp_settings: Settings):
    _setup_book_with_approved_ideas(tmp_settings)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")

    with get_connection(tmp_settings.db_path) as conn:
        rows = conn.execute("SELECT id FROM ideas WHERE status = 'approved' ORDER BY id").fetchall()
    idea_ids = [r["id"] for r in rows]

    # LLM only returns result for first idea, omits second
    mock_resp = _mock_review_response([
        {"id": idea_ids[0], "reviewed_quote": "Q1", "reviewed_quote_emphasis": None, "reviewed_comment": "C1"},
    ])

    with (
        patch("anne.cli.ideas.load_settings", return_value=settings_with_key),
        patch("anne.services.llm.urllib.request.urlopen", return_value=mock_resp),
    ):
        result = runner.invoke(app, ["idea-review", "test-book"])
    assert result.exit_code == 0
    assert "1 idea reviewed" in result.output

    # Verify: first idea reviewed, second stays approved
    with get_connection(tmp_settings.db_path) as conn:
        row = conn.execute("SELECT status FROM ideas WHERE id = ?", (idea_ids[0],)).fetchone()
        assert row["status"] == "reviewed"
        row = conn.execute("SELECT status FROM ideas WHERE id = ?", (idea_ids[1],)).fetchone()
        assert row["status"] == "approved"


# --- idea-caption tests ---


def _setup_book_with_reviewed_ideas(tmp_settings: Settings) -> None:
    """Create a book with reviewed ideas in the DB."""
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        book = create_book(conn, "Test Book", "Author")
        source = import_source(
            conn, book.id, SourceType.kindle_export_html, "sources/kindle/notes.html", "fp1"
        )
        ideas = insert_ideas(conn, book.id, source.id, [
            ParsedIdea(raw_quote="A great insight about the world", raw_note="My thought"),
            ParsedIdea(raw_quote="Another good idea", raw_note="With a note"),
        ])
        for idea in ideas:
            approve_idea(conn, idea.id)
            review_idea(
                conn, idea.id,
                reviewed_quote=f"Reviewed {idea.id}",
                reviewed_quote_emphasis=f"**Reviewed** {idea.id}",
                reviewed_comment=f"Context for {idea.id}.",
            )


def _mock_caption_response(results: list[dict]) -> MagicMock:
    body = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(results)}]}}
        ]
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_idea_caption_happy_path(tmp_settings: Settings):
    _setup_book_with_reviewed_ideas(tmp_settings)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")

    with get_connection(tmp_settings.db_path) as conn:
        rows = conn.execute("SELECT id FROM ideas WHERE status = 'reviewed' ORDER BY id").fetchall()
    idea_ids = [r["id"] for r in rows]

    mock_resp = _mock_caption_response([
        {"id": idea_ids[0], "presentation_text": "Hook line.\n\nCaption body.", "tags": ["poder", "ironia"]},
        {"id": idea_ids[1], "presentation_text": "Another hook.\n\nMore text.", "tags": ["melancolia"]},
    ])

    with (
        patch("anne.cli.ideas.load_settings", return_value=settings_with_key),
        patch("anne.services.llm.urllib.request.urlopen", return_value=mock_resp),
    ):
        result = runner.invoke(app, ["idea-caption", "test-book"])
    assert result.exit_code == 0
    assert "Captioned" in result.output
    assert "2 ideas captioned" in result.output

    # Verify DB state
    with get_connection(tmp_settings.db_path) as conn:
        row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_ids[0],)).fetchone()
        assert row["status"] == "ready"
        assert "Hook line" in row["presentation_text"]
        assert "poder" in row["tags"]

        row = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_ids[1],)).fetchone()
        assert row["status"] == "ready"


def test_idea_caption_no_reviewed_ideas(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        create_book(conn, "Empty Book", "Author")
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")
    with patch("anne.cli.ideas.load_settings", return_value=settings_with_key):
        result = runner.invoke(app, ["idea-caption", "empty-book"])
    assert result.exit_code == 0
    assert "no reviewed ideas" in result.output


def test_idea_caption_book_not_found(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")
    with patch("anne.cli.ideas.load_settings", return_value=settings_with_key):
        result = runner.invoke(app, ["idea-caption", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_idea_caption_missing_api_key(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    settings_no_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key=None)
    with patch("anne.cli.ideas.load_settings", return_value=settings_no_key):
        result = runner.invoke(app, ["idea-caption"])
    assert result.exit_code == 1
    assert "gemini_api_key" in result.output


def test_idea_caption_all_books(tmp_settings: Settings):
    _setup_book_with_reviewed_ideas(tmp_settings)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")

    with get_connection(tmp_settings.db_path) as conn:
        rows = conn.execute("SELECT id FROM ideas WHERE status = 'reviewed' ORDER BY id").fetchall()
    idea_ids = [r["id"] for r in rows]

    mock_resp = _mock_caption_response([
        {"id": idea_ids[0], "presentation_text": "Caption 1", "tags": ["mood"]},
        {"id": idea_ids[1], "presentation_text": "Caption 2", "tags": ["mood"]},
    ])

    with (
        patch("anne.cli.ideas.load_settings", return_value=settings_with_key),
        patch("anne.services.llm.urllib.request.urlopen", return_value=mock_resp),
    ):
        result = runner.invoke(app, ["idea-caption"])
    assert result.exit_code == 0
    assert "2 ideas captioned" in result.output


def test_idea_caption_rate_limited(tmp_settings: Settings):
    _setup_book_with_reviewed_ideas(tmp_settings)
    settings_with_key = Settings(root_dir=tmp_settings.root_dir, gemini_api_key="fake-key")

    with (
        patch("anne.cli.ideas.load_settings", return_value=settings_with_key),
        patch("anne.cli.ideas.caption_ideas_with_llm", side_effect=RateLimitError("rate limited")),
    ):
        result = runner.invoke(app, ["idea-caption", "test-book"])
    assert result.exit_code == 1
    assert "Rate limited" in result.output
    assert "Progress so far has been saved" in result.output
