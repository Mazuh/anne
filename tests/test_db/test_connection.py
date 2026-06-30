import sqlite3
from pathlib import Path

import pytest

from anne.db.connection import get_connection
from anne.utils.exceptions import WorkspaceAccessError


def test_connection_delete_journal_mode(tmp_path: Path):
    db_path = tmp_path / "test.db"
    with get_connection(db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "delete"


def test_connection_busy_timeout(tmp_path: Path):
    db_path = tmp_path / "test.db"
    with get_connection(db_path) as conn:
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert timeout == 5000


def test_connection_foreign_keys(tmp_path: Path):
    db_path = tmp_path / "test.db"
    with get_connection(db_path) as conn:
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1


def test_connection_row_factory(tmp_path: Path):
    db_path = tmp_path / "test.db"
    with get_connection(db_path) as conn:
        conn.execute("CREATE TABLE t (x TEXT)")
        conn.execute("INSERT INTO t VALUES ('hello')")
        row = conn.execute("SELECT x FROM t").fetchone()
        assert row["x"] == "hello"


def test_connection_access_denied_raises_workspace_access_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_path = tmp_path / "test.db"
    # Migrate once so the post-migration connect is the call that fails.
    with get_connection(db_path):
        pass

    def _denied(*_args, **_kwargs):
        raise sqlite3.OperationalError("authorization denied")

    monkeypatch.setattr(sqlite3, "connect", _denied)

    with pytest.raises(WorkspaceAccessError) as excinfo:
        with get_connection(db_path):
            pass
    assert excinfo.value.db_path == db_path
