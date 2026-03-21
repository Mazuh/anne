import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

_migrated_dbs: set[Path] = set()


@contextmanager
def get_connection(db_path: Path) -> Generator[sqlite3.Connection]:
    if db_path not in _migrated_dbs:
        from anne.db.migrate import apply_schema
        apply_schema(db_path)
        _migrated_dbs.add(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # DELETE journal mode instead of WAL: the workspace directory may live on
    # a cloud-synced folder (iCloud, Google Drive, OneDrive). WAL creates
    # -wal/-shm companion files that cloud services can sync out of order,
    # risking database corruption. DELETE mode uses a single rollback journal
    # file which is safer for cloud-synced directories.
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
