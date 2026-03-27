from anne.db.connection import get_connection
from anne.db.migrate import apply_schema, get_schema_version, CURRENT_VERSION


def test_apply_schema_creates_tables(tmp_settings):
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {r["name"] for r in tables}
        assert "books" in table_names
        assert "sources" in table_names
        assert "ideas" in table_names
        assert "schema_version" in table_names


def test_schema_version_set(tmp_settings):
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        version = get_schema_version(conn)
        assert version == CURRENT_VERSION


def test_apply_schema_idempotent(tmp_settings):
    apply_schema(tmp_settings.db_path)
    apply_schema(tmp_settings.db_path)
    with get_connection(tmp_settings.db_path) as conn:
        version = get_schema_version(conn)
        assert version == CURRENT_VERSION
