from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from anne.models import Idea, IdeaStatus

_COMMON_KEYS = """
[bold]Navigation[/bold]
  j/k  navigate
  n/p  next/prev page
  r    refresh

[bold]Filter & Search[/bold]
  f    filter status
  T    filter tag
  /    search

[bold]Pipeline[/bold]
  A    LLM actions
"""

_STATUS_ACTIONS: dict[str, str] = {
    "parsed": """[bold]Actions[/bold]
  a    triage
  x    reject
  c    copy field
""",
    "triaged": """[bold]Actions[/bold]
  e    edit field
  t    edit tags
  E    open in $EDITOR
  x    reject
  c    copy field
""",
    "reviewed": """[bold]Actions[/bold]
  e    edit field
  t    edit tags
  E    open in $EDITOR
  x    reject
  c    copy field
""",
    "ready": """[bold]Actions[/bold]
  P    publish
  e    edit field
  t    edit tags
  E    open in $EDITOR
  c    copy field
""",
    "published": """[bold]Actions[/bold]
  c    copy field
""",
    "rejected": """[bold]Actions[/bold]
  u    unreject
  c    copy field
""",
}

_BACK = """
  q    back
"""


class ActionPanel(VerticalScroll):
    DEFAULT_CSS = """
    ActionPanel {
        height: 1fr;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._content = Static(_COMMON_KEYS + _BACK, id="action-panel-content")

    def compose(self) -> ComposeResult:
        yield self._content

    def update_for_idea(self, idea: Idea | None) -> None:
        if idea is None:
            self._content.update(_COMMON_KEYS + _BACK)
            return
        status_actions = _STATUS_ACTIONS.get(idea.status, "")
        self._content.update(status_actions + _COMMON_KEYS + _BACK)
