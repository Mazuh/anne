from pathlib import Path

from anne.db.connection import get_connection


def test_connection_wal_mode(tmp_path: Path):
    db_path = tmp_path / "test.db"
    with get_connection(db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"


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
