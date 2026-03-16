from pathlib import Path
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from anne.cli.app import app
from anne.config.settings import Settings
from anne.db.migrate import apply_schema
from anne.services.filesystem import create_book_dirs

runner = CliRunner()


def _setup_book(tmp_settings: Settings) -> None:
    apply_schema(tmp_settings.db_path)
    with patch("anne.cli.books.load_settings", return_value=tmp_settings):
        runner.invoke(app, ["books", "add", "Test Book", "--author", "Author"])


def test_sources_import(tmp_settings: Settings, tmp_path: Path):
    _setup_book(tmp_settings)
    src_file = tmp_path / "notes.txt"
    src_file.write_text("some notes")

    with patch("anne.cli.sources.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["sources", "import", "test-book", str(src_file)])
    assert result.exit_code == 0
    assert "Imported" in result.output


def test_sources_import_duplicate(tmp_settings: Settings, tmp_path: Path):
    _setup_book(tmp_settings)
    src_file = tmp_path / "notes.txt"
    src_file.write_text("some notes")

    with patch("anne.cli.sources.load_settings", return_value=tmp_settings):
        runner.invoke(app, ["sources", "import", "test-book", str(src_file)])
        result = runner.invoke(app, ["sources", "import", "test-book", str(src_file)])
    assert result.exit_code == 0
    assert "Skipped" in result.output


def test_sources_import_book_not_found(tmp_settings: Settings, tmp_path: Path):
    apply_schema(tmp_settings.db_path)
    src_file = tmp_path / "notes.txt"
    src_file.write_text("data")

    with patch("anne.cli.sources.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["sources", "import", "nonexistent", str(src_file)])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_sources_list(tmp_settings: Settings, tmp_path: Path):
    _setup_book(tmp_settings)
    src_file = tmp_path / "notes.txt"
    src_file.write_text("some notes")

    with patch("anne.cli.sources.load_settings", return_value=tmp_settings):
        runner.invoke(app, ["sources", "import", "test-book", str(src_file)])
        result = runner.invoke(app, ["sources", "list", "test-book"])
    assert result.exit_code == 0
    assert "notes.txt" in result.output


def test_sources_import_url(tmp_settings: Settings):
    _setup_book(tmp_settings)

    mock_resp = MagicMock()
    mock_resp.read.return_value = b"<html><body>My essay content</body></html>"
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with (
        patch("anne.cli.sources.load_settings", return_value=tmp_settings),
        patch("anne.services.sources.urllib.request.urlopen", return_value=mock_resp),
    ):
        result = runner.invoke(app, ["sources", "import", "test-book", "https://example.com/p/my-essay"])
    assert result.exit_code == 0
    assert "Imported" in result.output
    assert "essay_html" in result.output


def test_sources_import_url_duplicate(tmp_settings: Settings):
    _setup_book(tmp_settings)

    mock_resp = MagicMock()
    mock_resp.read.return_value = b"<html><body>My essay</body></html>"
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with (
        patch("anne.cli.sources.load_settings", return_value=tmp_settings),
        patch("anne.services.sources.urllib.request.urlopen", return_value=mock_resp),
    ):
        runner.invoke(app, ["sources", "import", "test-book", "https://example.com/p/my-essay"])
        result = runner.invoke(app, ["sources", "import", "test-book", "https://example.com/p/my-essay"])
    assert result.exit_code == 0
    assert "Skipped" in result.output


def test_sources_list_empty(tmp_settings: Settings):
    _setup_book(tmp_settings)
    with patch("anne.cli.sources.load_settings", return_value=tmp_settings):
        result = runner.invoke(app, ["sources", "list", "test-book"])
    assert result.exit_code == 0
    assert "No sources found" in result.output
