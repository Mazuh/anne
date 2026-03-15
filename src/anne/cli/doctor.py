import shutil
import sys

import typer
from rich import print as rprint

from anne.config.settings import load_settings
from anne.db.connection import get_connection
from anne.db.migrate import CURRENT_VERSION, get_schema_version


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

    # FFmpeg
    if shutil.which("ffmpeg"):
        rprint("[green]\u2713[/green] FFmpeg available")
    else:
        rprint("[yellow]![/yellow] FFmpeg not found (needed for media generation)")

    # Books directory
    if settings.books_dir.exists():
        rprint(f"[green]\u2713[/green] Books directory: {settings.books_dir}")
    else:
        rprint(f"[red]\u2717[/red] Books directory missing: {settings.books_dir}")
        ok = False

    if ok:
        rprint("\n[green]All checks passed![/green]")
    else:
        rprint("\n[red]Some checks failed.[/red] Run [bold]anne bootstrap[/bold] to initialize.")
        raise typer.Exit(code=1)
