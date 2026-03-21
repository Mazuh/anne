from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from anne.cli.app import app
from anne.config.settings import Settings
from anne.db.migrate import apply_schema

runner = CliRunner()


def _make_workspace(tmp_path: Path) -> Settings:
    root = tmp_path / "anne"
    (root / "data").mkdir(parents=True)
    (root / "books").mkdir(parents=True)
    settings = Settings(root_dir=root, db_backup_dir=tmp_path / "backups")
    apply_schema(settings.db_path)
    return settings


def test_db_info(tmp_path: Path):
    settings = _make_workspace(tmp_path)
    with patch("anne.config.settings.load_settings", return_value=settings):
        with patch("anne.cli.db_cmd.load_settings", return_value=settings):
            result = runner.invoke(app, ["db", "info"])
    assert result.exit_code == 0
    assert "Database vs Filesystem" in result.output
    assert "Book metadata" in result.output


def test_db_backup_creates_file(tmp_path: Path):
    settings = _make_workspace(tmp_path)
    with patch("anne.cli.db_cmd.load_settings", return_value=settings):
        result = runner.invoke(app, ["db", "backup"])
    assert result.exit_code == 0
    assert "Backup created" in result.output
    backups = list((tmp_path / "backups").glob("anne-backup-*.db"))
    assert len(backups) == 1


def test_db_backup_never_overwrites(tmp_path: Path):
    settings = _make_workspace(tmp_path)
    filenames = iter(["anne-backup-20260101T000000Z.db", "anne-backup-20260101T000001Z.db"])
    with patch("anne.cli.db_cmd.load_settings", return_value=settings):
        with patch("anne.cli.db_cmd._backup_filename", side_effect=filenames):
            runner.invoke(app, ["db", "backup"])
            runner.invoke(app, ["db", "backup"])
    backups = list((tmp_path / "backups").glob("anne-backup-*.db"))
    assert len(backups) == 2


def test_db_backup_restore_from_latest(tmp_path: Path):
    settings = _make_workspace(tmp_path)

    # Insert some data, then backup
    from anne.db.connection import get_connection
    with get_connection(settings.db_path) as conn:
        conn.execute("INSERT INTO books (title, author, slug) VALUES ('Test', 'Author', 'test')")

    with patch("anne.cli.db_cmd.load_settings", return_value=settings):
        runner.invoke(app, ["db", "backup"])

    # Corrupt the DB by overwriting
    settings.db_path.write_text("corrupted")

    # Restore should recover
    with patch("anne.cli.db_cmd.load_settings", return_value=settings):
        result = runner.invoke(app, ["db", "backup-restore"])

    assert result.exit_code == 0
    assert "Restored from" in result.output
    assert "Books: 1" in result.output


def test_db_backup_restore_specific_path(tmp_path: Path):
    settings = _make_workspace(tmp_path)

    from anne.db.connection import get_connection
    with get_connection(settings.db_path) as conn:
        conn.execute("INSERT INTO books (title, author, slug) VALUES ('A', 'B', 'a')")

    # Manual backup to a custom location
    import shutil
    custom_backup = tmp_path / "my-backup.db"
    shutil.copy2(settings.db_path, custom_backup)

    # Wipe the DB
    settings.db_path.write_text("gone")

    with patch("anne.cli.db_cmd.load_settings", return_value=settings):
        result = runner.invoke(app, ["db", "backup-restore", str(custom_backup)])

    assert result.exit_code == 0
    assert "Restored from" in result.output


def test_db_backup_restore_no_backups(tmp_path: Path):
    settings = _make_workspace(tmp_path)
    with patch("anne.cli.db_cmd.load_settings", return_value=settings):
        result = runner.invoke(app, ["db", "backup-restore"])
    assert result.exit_code == 1
    assert "no backups found" in result.output
