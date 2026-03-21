import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich import print as rprint

from anne.config.settings import Settings, load_settings
from anne.db.connection import get_connection
from anne.db.migrate import get_schema_version

db_app = typer.Typer(help="Database management.")


def _backup_dir(settings: "Settings") -> Path:
    if settings.db_backup_dir is not None:
        return settings.db_backup_dir
    return settings.root_dir / "backups"


def _backup_filename() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"anne-backup-{ts}.db"


def _list_backups(backup_dir: Path) -> list[Path]:
    """Return backup files sorted by name descending (most recent first)."""
    if not backup_dir.is_dir():
        return []
    return sorted(backup_dir.glob("anne-backup-*.db"), reverse=True)


def _validate_backup(path: Path) -> int:
    """Open a backup file and return its schema version. Raises on invalid DB."""
    with get_connection(path) as conn:
        version = get_schema_version(conn)
        if version == 0:
            raise ValueError("file does not contain an Anne database (no schema_version)")
        return version


def _db_summary(path: Path) -> dict[str, int]:
    """Return counts of key tables in a database file."""
    # Table names are hardcoded below, not user input.
    tables = ("books", "sources", "ideas")
    counts: dict[str, int] = {}
    with get_connection(path) as conn:
        for table in tables:
            try:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                counts[table] = row[0]
            except sqlite3.OperationalError:
                counts[table] = 0
    return counts


@db_app.command("info")
def db_info() -> None:
    """Show what is stored in the database vs filesystem."""
    settings = load_settings()
    rprint("[bold]Database vs Filesystem[/bold]\n")
    rprint("[cyan]In the database (anne.db):[/cyan]")
    rprint("  - Book metadata (title, author, slug)")
    rprint("  - Source records (type, path, fingerprint — not the file content)")
    rprint("  - Ideas with all status, review data, tags, and captions")
    rprint("  - Asset and post metadata")
    rprint()
    rprint("[cyan]In the filesystem (books/ directory):[/cyan]")
    rprint("  - Actual source files (Kindle exports, essays, notes)")
    rprint("  - Asset files (images, videos)")
    rprint("  - Post outputs")
    rprint()
    rprint("[yellow]Why backups matter:[/yellow]")
    rprint("  Source files are the ground truth and can be re-imported.")
    rprint("  But reviewed ideas, tags, captions, and status are DB-only —")
    rprint("  they would be lost without a backup if the database corrupts.")
    rprint()
    rprint("  This is especially important if your workspace is on a cloud-synced")
    rprint("  folder (iCloud, Google Drive, OneDrive), where SQLite corruption")
    rprint("  is a known risk. Regular backups via [bold]anne db backup[/bold] are")
    rprint("  recommended as a pragmatic safeguard.")
    rprint()
    rprint(f"  Database path: {settings.db_path}")
    backup_dir = _backup_dir(settings)
    rprint(f"  Backup directory: {backup_dir}")
    backups = _list_backups(backup_dir)
    if backups:
        rprint(f"  Backups available: {len(backups)} (latest: {backups[0].name})")
    else:
        rprint("  Backups available: none")


@db_app.command("backup")
def db_backup(
    dest: Path | None = typer.Option(None, "--dest", help="Custom backup destination directory"),
) -> None:
    """Create a timestamped backup of the database."""
    settings = load_settings()
    if not settings.db_path.exists():
        rprint("[red]Error:[/red] database not found. Run [bold]anne bootstrap[/bold] first.")
        raise typer.Exit(code=1)

    backup_dir = dest if dest is not None else _backup_dir(settings)
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_path = backup_dir / _backup_filename()

    # Use SQLite backup API instead of file copy to ensure consistency
    # even if the database is open in another process (e.g. the TUI).
    src_conn = sqlite3.connect(str(settings.db_path))
    dst_conn = sqlite3.connect(str(backup_path))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    rprint(f"[green]Backup created:[/green] {backup_path}")
    counts = _db_summary(backup_path)
    rprint(f"  Books: {counts['books']}, Sources: {counts['sources']}, Ideas: {counts['ideas']}")


@db_app.command("backup-restore")
def db_backup_restore(
    path: Path | None = typer.Argument(None, help="Path to backup file (uses latest if omitted)"),
) -> None:
    """Restore the database from a backup file."""
    settings = load_settings()

    if path is not None:
        backup_path = path
    else:
        backup_dir = _backup_dir(settings)
        backups = _list_backups(backup_dir)
        if not backups:
            rprint(f"[red]Error:[/red] no backups found in {backup_dir}")
            raise typer.Exit(code=1)
        backup_path = backups[0]
        rprint(f"Using latest backup: {backup_path.name}")

    if not backup_path.exists():
        rprint(f"[red]Error:[/red] backup file not found: {backup_path}")
        raise typer.Exit(code=1)

    # Validate
    try:
        version = _validate_backup(backup_path)
    except (sqlite3.DatabaseError, ValueError) as e:
        rprint(f"[red]Error:[/red] invalid backup file: {e}")
        raise typer.Exit(code=1)

    # Safety backup of current DB before overwriting
    if settings.db_path.exists():
        safety_dir = _backup_dir(settings)
        safety_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safety_path = safety_dir / f"anne-pre-restore-{ts}.db"
        shutil.copy2(settings.db_path, safety_path)
        rprint(f"[dim]Safety backup of current DB: {safety_path}[/dim]")

    # Restore
    shutil.copy2(backup_path, settings.db_path)

    counts = _db_summary(settings.db_path)
    rprint(f"[green]Restored from:[/green] {backup_path}")
    rprint(f"  Schema version: {version}")
    rprint(f"  Books: {counts['books']}, Sources: {counts['sources']}, Ideas: {counts['ideas']}")
