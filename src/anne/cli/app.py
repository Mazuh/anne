import typer

from anne.cli.bootstrap import bootstrap
from anne.cli.doctor import doctor
from anne.cli import books as books_module
from anne.cli import sources as sources_module
from anne.cli.ideas import idea_triage, idea_parse, idea_review, idea_caption

app = typer.Typer(help="Anne — pipeline CLI for turning reading notes into posts.")

app.command()(bootstrap)
app.command()(doctor)
app.command("idea-parse")(idea_parse)
app.command("idea-triage")(idea_triage)
app.command("idea-review")(idea_review)
app.command("idea-caption")(idea_caption)
app.add_typer(books_module.app, name="books")
app.add_typer(sources_module.app, name="sources")
