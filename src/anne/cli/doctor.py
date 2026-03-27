import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich import print as rprint

from anne.config.settings import load_settings
from anne.db.connection import get_connection
from anne.db.migrate import CURRENT_VERSION, get_schema_version
from anne.utils.icloud import find_evicted_files


def doctor() -> None:
    """Check Anne workspace health."""
    ok = True

    # Python version
    v = sys.version_info
    if v >= (3, 14):
        rprint(f"[green]\u2713[/green] Python {v.major}.{v.minor}.{v.micro}")
    else:
        rprint(f"[red]\u2717[/red] Python {v.major}.{v.minor}.{v.micro} (need >= 3.14)")
        ok = False

    settings = load_settings()

    # Root directory
    if settings.root_dir.exists() and settings.root_dir.is_dir():
        rprint(f"[green]\u2713[/green] Root directory: {settings.root_dir}")
    else:
        rprint(f"[red]\u2717[/red] Root directory missing: {settings.root_dir}")
        ok = False

    # Database
    if settings.db_path.exists():
        rprint(f"[green]\u2713[/green] Database: {settings.db_path}")
        try:
            with get_connection(settings.db_path) as conn:
                version = get_schema_version(conn)
                if version >= CURRENT_VERSION:
                    rprint(f"[green]\u2713[/green] Schema version: {version}")
                else:
                    rprint(f"[yellow]![/yellow] Schema version {version} (current: {CURRENT_VERSION})")
                    ok = False
        except Exception as e:
            rprint(f"[red]\u2717[/red] Database error: {e}")
            ok = False
    else:
        rprint(f"[red]\u2717[/red] Database missing: {settings.db_path}")
        ok = False

    # Books directory
    if settings.books_dir.exists():
        rprint(f"[green]\u2713[/green] Books directory: {settings.books_dir}")
    else:
        rprint(f"[red]\u2717[/red] Books directory missing: {settings.books_dir}")
        ok = False

    # Cloud storage detection
    root_str = str(settings.root_dir)
    home = str(Path.home())
    is_cloud = root_str.startswith(os.path.join(home, "Library/Mobile Documents"))
    if is_cloud:
        rprint("[cyan]ℹ[/cyan] Workspace appears to be on a cloud-synced folder (iCloud)")
    elif root_str.startswith(os.path.join(home, "Documents")):
        rprint("[cyan]ℹ[/cyan] Workspace is in ~/Documents — if this folder is cloud-synced,"
               " consider running [bold]anne db backup[/bold] regularly")

    # Evicted source files
    if settings.books_dir.exists():
        evicted = find_evicted_files(settings.books_dir)
        if evicted:
            rprint(f"[yellow]![/yellow] {len(evicted)} source file(s) evicted by cloud storage")
        else:
            rprint("[green]✓[/green] No evicted source files")

    # Backup freshness
    if settings.db_backup_dir is not None:
        from anne.cli.db_cmd import _list_backups
        backups = _list_backups(settings.db_backup_dir)
        if not backups:
            rprint("[yellow]![/yellow] No database backups found — run [bold]anne db backup[/bold]")
        else:
            latest = backups[0]
            mtime = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)
            age_days = (datetime.now(timezone.utc) - mtime).days
            if age_days > 7:
                rprint(f"[yellow]![/yellow] Latest backup is {age_days} days old: {latest.name}")
            else:
                rprint(f"[green]✓[/green] Latest backup: {latest.name} ({age_days}d ago)")

    # Shell alias
    from anne.cli.bootstrap import PROJECT_DIR

    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        rc_file = "~/.zshrc"
    elif "bash" in shell:
        rc_file = "~/.bashrc"
    else:
        rc_file = "your shell config"

    alias_line = f'alias anne="uv run --project {PROJECT_DIR} anne"'
    alias_configured = False
    rc_path = Path(rc_file).expanduser()
    if rc_path.exists() and alias_line in rc_path.read_text():
        rprint("[green]\u2713[/green] Shell alias configured")
        alias_configured = True
    else:
        rprint(f"[yellow]![/yellow] Shell alias not found in {rc_file}")

    if ok:
        rprint("\n[green]All checks passed![/green]")
        if not alias_configured:
            rprint(f"\n[dim]Tip: to make [bold]anne[/bold] available globally, add to {rc_file}:[/dim]")
            rprint(f"[dim]  {alias_line}[/dim]")
    else:
        rprint("\n[red]Some checks failed.[/red] Run [bold]anne bootstrap[/bold] to initialize.")
        raise typer.Exit(code=1)
