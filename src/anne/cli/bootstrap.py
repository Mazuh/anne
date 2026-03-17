import os
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

    (root_dir / "data").mkdir(parents=True, exist_ok=True)
    (root_dir / "books").mkdir(parents=True, exist_ok=True)

    settings = Settings(
        root_dir=root_dir,
        gemini_api_key=gemini_key or None,
        cta_link=cta_link,
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
