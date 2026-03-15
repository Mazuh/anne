import typer

from anne.cli.bootstrap import bootstrap
from anne.cli.doctor import doctor
from anne.cli import books as books_module
from anne.cli import sources as sources_module

app = typer.Typer(help="Anne — pipeline CLI for turning reading notes into posts.")

app.command()(bootstrap)
app.command()(doctor)
app.add_typer(books_module.app, name="books")
app.add_typer(sources_module.app, name="sources")
