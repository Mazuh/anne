from pathlib import Path

import typer
from rich import print as rprint

from anne.config.settings import Settings, save_settings
from anne.db.migrate import apply_schema


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
