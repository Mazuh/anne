import json

from rich.markup import escape

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from anne.models import Idea, IdeaStatus


def _render_idea(idea: Idea, book_title: str, source_path: str) -> str:
    lines: list[str] = []

    lines.append(f"[bold]Idea #{idea.id}[/bold]  [{_status_color(idea.status)}]{idea.status}[/]")
    lines.append(f"  Book:    {_escape(book_title)}")
    lines.append(f"  Source:  {_escape(source_path)}")
    if idea.raw_ref:
        lines.append(f"  Ref:     {_escape(idea.raw_ref)}")
    lines.append(f"  Created: {idea.created_at}")
    lines.append(f"  Updated: {idea.updated_at}")
    if idea.published_at:
        lines.append(f"  Published: {idea.published_at}")
    lines.append(f"  Tags:    {_format_tags(idea.tags)}")

    if idea.raw_quote or idea.raw_note:
        lines.append("")
        lines.append("[bold]Raw[/bold]")
        if idea.raw_quote:
            lines.append(f'  Quote: "{_escape(idea.raw_quote)}"')
        if idea.raw_note:
            lines.append(f"  Note:  {_escape(idea.raw_note)}")

    if idea.status == IdeaStatus.rejected and idea.rejection_reason:
        lines.append("")
        lines.append("[bold]Triage[/bold]")
        lines.append(f"  Rejection reason: {_escape(idea.rejection_reason)}")

    if idea.reviewed_quote or idea.reviewed_comment:
        lines.append("")
        lines.append("[bold]Review[/bold]")
        if idea.reviewed_quote:
            lines.append(f'  Quote:   "{_escape(idea.reviewed_quote)}"')
        if idea.reviewed_comment:
            lines.append(f"  Comment:  {_escape(idea.reviewed_comment)}")

    if idea.presentation_text:
        lines.append("")
        lines.append("[bold]Caption[/bold]")
        lines.append(f"  Text: {_escape(idea.presentation_text)}")

    return "\n".join(lines)


def _status_color(status: str) -> str:
    colors = {
        "parsed": "bright_blue",
        "triaged": "yellow",
        "reviewed": "cyan",
        "ready": "green",
        "queued": "bright_yellow",
        "published": "bright_green",
        "rejected": "red",
    }
    return colors.get(status, "white")


def _format_tags(tags: str) -> str:
    if not tags or tags == "[]":
        return "\u2014"
    try:
        tag_list = json.loads(tags)
        if tag_list:
            return ", ".join(str(t) for t in tag_list)
    except (json.JSONDecodeError, TypeError):
        return _escape(tags)
    return "\u2014"


def _escape(text: str) -> str:
    return escape(text)


class IdeaDetail(VerticalScroll):
    DEFAULT_CSS = """
    IdeaDetail {
        height: 1fr;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._content = Static("Select an idea to view details.", id="idea-detail-content")

    def compose(self) -> ComposeResult:
        yield self._content

    def show_idea(self, idea: Idea, book_title: str, source_path: str) -> None:
        rendered = _render_idea(idea, book_title, source_path)
        self._content.update(rendered)
        self.scroll_home(animate=False)

    def show_empty(self, message: str = "No idea selected.") -> None:
        self._content.update(message)
