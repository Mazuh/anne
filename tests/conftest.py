from pathlib import Path

import pytest

from anne.config.settings import Settings
from anne.db.connection import get_connection
from anne.db.migrate import apply_schema


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    root = tmp_path / "anne"
    (root / "data").mkdir(parents=True)
    (root / "books").mkdir(parents=True)
    return root


@pytest.fixture
def tmp_settings(tmp_root: Path) -> Settings:
    return Settings(root_dir=tmp_root)


@pytest.fixture
def tmp_db(tmp_settings: Settings):
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        yield conn
