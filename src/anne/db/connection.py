import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


@contextmanager
def get_connection(db_path: Path) -> Generator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
