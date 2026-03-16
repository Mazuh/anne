import os
from pathlib import Path

import typer
from rich import print as rprint

from anne.config.settings import Settings, save_settings
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
    default = str(Path.home() / "Documents" / "anne")
    root_str = typer.prompt("Root directory for Anne workspace", default=default)
    root_dir = Path(root_str).expanduser().resolve()

    if root_dir.exists():
        rprint(f"[red]Error:[/red] folder already exists: {root_dir}")
        rprint("Remove it first or choose a different location.")
        raise typer.Exit(code=1)

    (root_dir / "data").mkdir(parents=True)
    (root_dir / "books").mkdir(parents=True)

    settings = Settings(root_dir=root_dir)
    save_settings(settings)

    apply_schema(settings.db_path)

    rprint(f"[green]Anne workspace created at:[/green] {root_dir}")
    rprint(f"  Database: {settings.db_path}")
    rprint(f"  Books:    {settings.books_dir}")
    rprint(f"  Config:   {settings.root_dir}")
    rprint("\n[green]Bootstrap complete![/green] Run [bold]anne doctor[/bold] to verify.")

    _print_shell_hint()
