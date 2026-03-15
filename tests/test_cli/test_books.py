from unittest.mock import patch

from typer.testing import CliRunner

from anne.cli.app import app
from anne.config.settings import Settings
from anne.db.migrate import apply_schema

runner = CliRunner()


def test_books_add(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with patch("anne.cli.books.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["books", "add", "O Príncipe", "--author", "Maquiavel"])
    assert result.exit_code == 0
    assert "o-principe" in result.output


def test_books_list_empty(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with patch("anne.cli.books.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["books", "list"])
    assert result.exit_code == 0
    assert "No books found" in result.output


def test_books_list_with_books(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with patch("anne.cli.books.load_settings", return_value=tmp_settings):
        runner.invoke(app, ["books", "add", "Test Book", "--author", "Author"])
        result = runner.invoke(app, ["books", "list"])
    assert result.exit_code == 0
    assert "test-book" in result.output


def test_books_show(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with patch("anne.cli.books.load_settings", return_value=tmp_settings):
        runner.invoke(app, ["books", "add", "My Book", "--author", "Author"])
        result = runner.invoke(app, ["books", "show", "my-book"])
    assert result.exit_code == 0
    assert "My Book" in result.output


def test_books_show_not_found(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with patch("anne.cli.books.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["books", "show", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output
