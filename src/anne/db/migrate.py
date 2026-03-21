import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
CURRENT_VERSION = 3


def get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        return row[0] if row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


_IDEAS_COLUMNS = (
    "id, book_id, source_id, status, raw_quote, raw_note, raw_ref, "
    "rejection_reason, reviewed_quote, "
    "reviewed_comment, quick_context, presentation_text, tags, "
    "created_at, updated_at"
)

# Includes the reviewed_quote_emphasis column that existed in schema v2.
_IDEAS_COLUMNS_WITH_EMPHASIS = (
    "id, book_id, source_id, status, raw_quote, raw_note, raw_ref, "
    "rejection_reason, reviewed_quote, reviewed_quote_emphasis, "
    "reviewed_comment, quick_context, presentation_text, tags, "
    "created_at, updated_at"
)


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Make raw_quote nullable: recreate ideas table.

    Note: table recreation drops any indexes/triggers on 'ideas'.
    Re-create them explicitly after the rename if added in the future.
    """
    # Drop leftover temp table from a previously interrupted migration.
    conn.execute("DROP TABLE IF EXISTS ideas_new")
    conn.execute("""
        CREATE TABLE ideas_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL REFERENCES books(id),
            source_id INTEGER NOT NULL REFERENCES sources(id),
            status TEXT NOT NULL DEFAULT 'parsed',
            raw_quote TEXT,
            raw_note TEXT,
            raw_ref TEXT,
            rejection_reason TEXT,
            reviewed_quote TEXT,
            reviewed_quote_emphasis TEXT,
            reviewed_comment TEXT,
            quick_context TEXT,
            presentation_text TEXT,
            tags TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute(f"INSERT INTO ideas_new ({_IDEAS_COLUMNS_WITH_EMPHASIS}) SELECT {_IDEAS_COLUMNS_WITH_EMPHASIS} FROM ideas")
    conn.execute("DROP TABLE ideas")
    conn.execute("ALTER TABLE ideas_new RENAME TO ideas")


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """Merge reviewed_quote_emphasis into reviewed_quote and drop the column.

    Copies emphasis text (which includes **bold** markers) into reviewed_quote
    where emphasis was set, then rebuilds the table without the column.
    """
    # Merge emphasis into reviewed_quote; safe to re-run if already migrated
    # (the column may no longer exist if a prior run partially succeeded).
    try:
        conn.execute("""
            UPDATE ideas SET reviewed_quote = reviewed_quote_emphasis
            WHERE reviewed_quote_emphasis IS NOT NULL
        """)
    except sqlite3.OperationalError:
        pass  # column already dropped by a prior incomplete migration

    # Drop leftover temp table from a previously interrupted migration.
    conn.execute("DROP TABLE IF EXISTS ideas_new")
    conn.execute("""
        CREATE TABLE ideas_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL REFERENCES books(id),
            source_id INTEGER NOT NULL REFERENCES sources(id),
            status TEXT NOT NULL DEFAULT 'parsed',
            raw_quote TEXT,
            raw_note TEXT,
            raw_ref TEXT,
            rejection_reason TEXT,
            reviewed_quote TEXT,
            reviewed_comment TEXT,
            quick_context TEXT,
            presentation_text TEXT,
            tags TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute(f"INSERT INTO ideas_new ({_IDEAS_COLUMNS}) SELECT {_IDEAS_COLUMNS} FROM ideas")
    conn.execute("DROP TABLE ideas")
    conn.execute("ALTER TABLE ideas_new RENAME TO ideas")


def apply_schema(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        version = get_schema_version(conn)
        if version >= CURRENT_VERSION:
            return

        if version == 0:
            schema_sql = SCHEMA_PATH.read_text()
            conn.executescript(schema_sql)
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (CURRENT_VERSION,),
            )
            conn.commit()
            return

        if version < 2:
            _migrate_v1_to_v2(conn)
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (2,),
            )
            conn.commit()
        if version < 3:
            _migrate_v2_to_v3(conn)
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (3,),
            )
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
