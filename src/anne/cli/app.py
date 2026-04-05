import typer

from anne import APP_AUTHOR, APP_DESCRIPTION, APP_REPO
from anne.cli.bootstrap import bootstrap
from anne.cli.doctor import doctor
from anne.cli import books as books_module
from anne.cli import sources as sources_module
from anne.cli.ideas import ideas_app
from anne.cli.db_cmd import db_app
from anne.cli.review import start_tui

app = typer.Typer(
    help=f"Anne — {APP_DESCRIPTION}\n\nBy {APP_AUTHOR}.\nSource: {APP_REPO}",
)

app.command()(bootstrap)
app.command()(doctor)
app.add_typer(books_module.app, name="books")
app.add_typer(sources_module.app, name="sources")
app.add_typer(ideas_app, name="ideas")
app.add_typer(db_app, name="db")
app.command("start")(start_tui)
