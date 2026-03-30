import os
import subprocess
from pathlib import Path

import typer
from rich import print as rprint

from anne.config.settings import Settings, load_settings, save_settings
from anne.db.migrate import apply_schema

PROJECT_DIR = Path(__file__).resolve().parents[3]


def _print_shell_hint() -> None:
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        rc_file = "~/.zshrc"
    elif "bash" in shell:
        rc_file = "~/.bashrc"
    else:
        rc_file = "your shell config"

    rprint(f"\n[dim]Tip: to make [bold]anne[/bold] available globally, add to {rc_file}:[/dim]")
    rprint(f'[dim]  alias anne="uv run --project {PROJECT_DIR} anne"[/dim]')


def bootstrap() -> None:
    """Initialize Anne workspace and configuration."""
    rprint("[dim]Syncing dependencies...[/dim]")
    result = subprocess.run(["uv", "sync", "--project", str(PROJECT_DIR)])
    if result.returncode != 0:
        rprint("[yellow]Warning: uv sync failed. Continuing anyway.[/yellow]")

    existing = load_settings()

    root_str = typer.prompt("Root directory for Anne workspace", default=str(existing.root_dir))
    root_dir = Path(root_str).expanduser().resolve()

    rprint("[dim]Get a Gemini API key at https://aistudio.google.com/apikey[/dim]")
    existing_key = existing.gemini_api_key
    if existing_key:
        masked = "..." + existing_key[-4:] if len(existing_key) > 4 else "***"
        gemini_key = typer.prompt("Gemini API key", default=masked).strip()
        if gemini_key == masked:
            gemini_key = existing_key
    else:
        gemini_key = typer.prompt("Gemini API key").strip()

    cta_link = typer.prompt(
        "CTA link for captions (e.g. Substack URL, leave blank to skip)",
        default=existing.cta_link or "",
    ).strip()

    rprint("\n[dim]The database holds idea reviews, tags, and captions — data that[/dim]")
    rprint("[dim]cannot be rebuilt from source files. If your workspace is on a[/dim]")
    rprint("[dim]cloud-synced folder, regular backups are recommended.[/dim]")
    backup_default = str(existing.db_backup_dir) if existing.db_backup_dir else ""
    backup_str = typer.prompt(
        "Database backup directory (leave blank to skip)",
        default=backup_default,
    ).strip()
    db_backup_dir = Path(backup_str).expanduser().resolve() if backup_str else None

    (root_dir / "data").mkdir(parents=True, exist_ok=True)
    (root_dir / "books").mkdir(parents=True, exist_ok=True)
    if db_backup_dir is not None:
        db_backup_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        root_dir=root_dir,
        gemini_api_key=gemini_key or None,
        cta_link=cta_link,
        db_backup_dir=db_backup_dir,
    )
    save_settings(settings)

    apply_schema(settings.db_path)

    rprint(f"[green]Anne workspace ready at:[/green] {root_dir}")
    rprint(f"  Database: {settings.db_path}")
    rprint(f"  Books:    {settings.books_dir}")
    if settings.gemini_api_key:
        rprint(f"  Gemini:   [green]configured[/green]")
    else:
        rprint(f"  Gemini:   [yellow]not configured[/yellow]")
    rprint("\n[green]Bootstrap complete![/green] Run [bold]anne doctor[/bold] to verify.")

    _print_shell_hint()
