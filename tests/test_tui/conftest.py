from pathlib import Path

import pytest
from textual.app import App

from anne.config.settings import Settings
from anne.db.connection import get_connection
from anne.db.migrate import apply_schema
from anne.models import SourceType
from anne.services.books import create_book
from anne.services.ideas import insert_ideas
from anne.services.parsers import ParsedIdea
from anne.services.sources import import_source


@pytest.fixture
def tui_root(tmp_path: Path) -> Path:
    root = tmp_path / "anne"
    (root / "data").mkdir(parents=True)
    (root / "books").mkdir(parents=True)
    return root


@pytest.fixture
def tui_settings(tui_root: Path) -> Settings:
    return Settings(root_dir=tui_root)


@pytest.fixture
def empty_settings(tui_settings: Settings) -> Settings:
    """Settings with schema applied but no data."""
    apply_schema(tui_settings.db_path)
    return tui_settings


@pytest.fixture
def seeded_settings(tui_settings: Settings) -> Settings:
    """Settings with a seeded database containing a book, source, and ideas."""
    apply_schema(tui_settings.db_path)

    with get_connection(tui_settings.db_path) as conn:
        book = create_book(conn, "Test Book", "Test Author")

        source = import_source(
            conn,
            book.id,
            SourceType.kindle_export_html,
            "sources/kindle/notes.html",
            "abc123fingerprint",
        )

        ideas = [
            ParsedIdea(raw_quote=f"Quote {i}", raw_note=f"Note {i}", raw_ref=f"Ch.{i}")
            for i in range(1, 11)
        ]
        insert_ideas(conn, book.id, source.id, ideas)

    return tui_settings


async def wait_for_workers(app: App) -> None:
    """Wait for all background workers to complete."""
    await app.workers.wait_for_complete()
