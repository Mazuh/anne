import sqlite3
from pathlib import Path

from anne.db.connection import get_connection

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
CURRENT_VERSION = 1


def get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        return row[0] if row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def apply_schema(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        version = get_schema_version(conn)
        if version >= CURRENT_VERSION:
            return
        schema_sql = SCHEMA_PATH.read_text()
        conn.executescript(schema_sql)
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (CURRENT_VERSION,),
        )
