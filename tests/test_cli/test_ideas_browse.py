import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from anne.cli.app import app
from anne.config.settings import Settings
from anne.db.connection import get_connection
from anne.db.migrate import apply_schema
from anne.models import IdeaStatus, SourceType
from anne.services.books import create_book
from anne.services.ideas import insert_ideas, triage_approve_idea, review_idea, caption_idea
from anne.services.parsers import ParsedIdea
from anne.services.sources import import_source

runner = CliRunner()


def _setup_ideas(tmp_settings: Settings, count: int = 5, status: str = "parsed") -> list[int]:
    """Create a book with ideas at the given status. Returns idea IDs."""
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        book = create_book(conn, "Test Book", "Author")
        source = import_source(
            conn, book.id, SourceType.kindle_export_html, "sources/test.html", "fp1"
        )
        parsed = [
            ParsedIdea(raw_quote=f"Quote number {i}", raw_note=f"Note {i}", raw_ref=f"Ch.{i}")
            for i in range(1, count + 1)
        ]
        ideas = insert_ideas(conn, book.id, source.id, parsed)

        if status in ("triaged", "reviewed", "ready"):
            for idea in ideas:
                triage_approve_idea(conn, idea.id)
        if status in ("reviewed", "ready"):
            for idea in ideas:
                review_idea(conn, idea.id, f"Reviewed {idea.id}", f"Comment {idea.id}")
        if status == "ready":
            for idea in ideas:
                caption_idea(conn, idea.id, f"Caption {idea.id}", '["tag"]')

        return [idea.id for idea in ideas]


# --- ideas list ---


def test_ideas_list_all(tmp_settings: Settings):
    _setup_ideas(tmp_settings, 3)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "list"])
    assert result.exit_code == 0
    assert "Quote number 1" in result.output
    assert "3 total ideas" in result.output


def test_ideas_list_by_book(tmp_settings: Settings):
    _setup_ideas(tmp_settings, 3)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "list", "test-book"])
    assert result.exit_code == 0
    assert "Test Book" in result.output
    assert "3 total ideas" in result.output


def test_ideas_list_filter_status(tmp_settings: Settings):
    _setup_ideas(tmp_settings, 3)
    # All are parsed, none triaged
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "list", "--status", "triaged"])
    assert result.exit_code == 0
    assert "No ideas found" in result.output


def test_ideas_list_filter_status_match(tmp_settings: Settings):
    _setup_ideas(tmp_settings, 3, status="triaged")
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "list", "--status", "triaged"])
    assert result.exit_code == 0
    assert "3 total ideas" in result.output


def test_ideas_list_pagination(tmp_settings: Settings):
    _setup_ideas(tmp_settings, 5)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "list", "--per-page", "2", "--page", "1"])
    assert result.exit_code == 0
    assert "Page 1/3" in result.output
    assert "5 total ideas" in result.output


def test_ideas_list_page_out_of_range(tmp_settings: Settings):
    _setup_ideas(tmp_settings, 2)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "list", "--page", "5"])
    assert result.exit_code == 1
    assert "exceeds total pages" in result.output


def test_ideas_list_book_not_found(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "list", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_ideas_list_empty(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "list"])
    assert result.exit_code == 0
    assert "No ideas found" in result.output


def test_ideas_list_no_book_column_when_filtered(tmp_settings: Settings):
    """When book-slug is given, Book column should NOT appear."""
    _setup_ideas(tmp_settings, 2)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "list", "test-book"])
    assert result.exit_code == 0
    # The "Book" column header should not be in the table
    # But "Test Book" appears in the title, not as a column value
    lines = result.output.split("\n")
    # Find the header row (contains "ID" and "Status")
    header_lines = [l for l in lines if "Status" in l and "ID" in l]
    if header_lines:
        assert "Book" not in header_lines[0]


# --- ideas show ---


def test_ideas_show(tmp_settings: Settings):
    ids = _setup_ideas(tmp_settings, 1)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "show", str(ids[0])])
    assert result.exit_code == 0
    assert f"Idea #{ids[0]}" in result.output
    assert "Quote number 1" in result.output
    assert "Note 1" in result.output
    assert "Ch.1" in result.output
    assert "Test Book" in result.output


def test_ideas_show_reviewed(tmp_settings: Settings):
    ids = _setup_ideas(tmp_settings, 1, status="reviewed")
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "show", str(ids[0])])
    assert result.exit_code == 0
    assert "Review" in result.output
    assert f"Reviewed {ids[0]}" in result.output
    assert f"Comment {ids[0]}" in result.output


def test_ideas_show_ready(tmp_settings: Settings):
    ids = _setup_ideas(tmp_settings, 1, status="ready")
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "show", str(ids[0])])
    assert result.exit_code == 0
    assert "Caption" in result.output
    assert f"Caption {ids[0]}" in result.output


def test_ideas_show_not_found(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "show", "9999"])
    assert result.exit_code == 1
    assert "not found" in result.output


# --- ideas edit ---


def test_ideas_edit_raw_quote(tmp_settings: Settings):
    ids = _setup_ideas(tmp_settings, 1)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "edit", str(ids[0]), "--raw-quote", "New quote"])
    assert result.exit_code == 0
    assert "Updated" in result.output

    # Verify DB
    with get_connection(tmp_settings.db_path) as conn:
        row = conn.execute("SELECT raw_quote FROM ideas WHERE id = ?", (ids[0],)).fetchone()
        assert row["raw_quote"] == "New quote"


def test_ideas_edit_status_valid(tmp_settings: Settings):
    ids = _setup_ideas(tmp_settings, 1)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "edit", str(ids[0]), "--status", "triaged"])
    assert result.exit_code == 0
    assert "triaged" in result.output


def test_ideas_edit_status_invalid(tmp_settings: Settings):
    ids = _setup_ideas(tmp_settings, 1)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "edit", str(ids[0]), "--status", "reviewed"])
    assert result.exit_code == 1
    assert "Invalid status transition" in result.output


def test_ideas_edit_status_force(tmp_settings: Settings):
    ids = _setup_ideas(tmp_settings, 1)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "edit", str(ids[0]), "--status", "ready", "--force"])
    assert result.exit_code == 0
    assert "ready" in result.output


def test_ideas_edit_tags(tmp_settings: Settings):
    ids = _setup_ideas(tmp_settings, 1)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "edit", str(ids[0]), "--tags", '["a", "b"]'])
    assert result.exit_code == 0

    with get_connection(tmp_settings.db_path) as conn:
        row = conn.execute("SELECT tags FROM ideas WHERE id = ?", (ids[0],)).fetchone()
        assert json.loads(row["tags"]) == ["a", "b"]


def test_ideas_edit_invalid_tags(tmp_settings: Settings):
    ids = _setup_ideas(tmp_settings, 1)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "edit", str(ids[0]), "--tags", "not json"])
    assert result.exit_code == 1


def test_ideas_edit_not_found(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "edit", "9999", "--raw-quote", "x"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_ideas_edit_no_fields(tmp_settings: Settings):
    ids = _setup_ideas(tmp_settings, 1)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["ideas", "edit", str(ids[0])])
    assert result.exit_code == 1
    assert "at least one field" in result.output


def test_ideas_edit_multiple_fields(tmp_settings: Settings):
    ids = _setup_ideas(tmp_settings, 1)
    with patch("anne.cli.ideas.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, [
            "ideas", "edit", str(ids[0]),
            "--raw-quote", "New Q",
            "--raw-note", "New N",
        ])
    assert result.exit_code == 0

    with get_connection(tmp_settings.db_path) as conn:
        row = conn.execute("SELECT raw_quote, raw_note FROM ideas WHERE id = ?", (ids[0],)).fetchone()
        assert row["raw_quote"] == "New Q"
        assert row["raw_note"] == "New N"
