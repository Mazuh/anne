from textual.widgets import Static

from anne.models import IdeaStatus


class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(" ", **kwargs)
        self._status_filter: IdeaStatus | None = None
        self._page = 1
        self._total_pages = 1
        self._total_ideas = 0
        self._search_query = ""
        self._tag_filter: str | None = None

    def refresh_bar(
        self,
        *,
        status_filter: IdeaStatus | None = None,
        page: int = 1,
        total_pages: int = 1,
        total_ideas: int = 0,
        search_query: str = "",
        tag_filter: str | None = None,
    ) -> None:
        self._status_filter = status_filter
        self._page = page
        self._total_pages = total_pages
        self._total_ideas = total_ideas
        self._search_query = search_query
        self._tag_filter = tag_filter
        self._update_display()

    def _update_display(self) -> None:
        parts: list[str] = []

        if self._status_filter:
            parts.append(f"\\[{self._status_filter.value}]")
        else:
            parts.append("\\[all]")

        if self._tag_filter:
            parts.append(f"tag:{self._tag_filter}")

        parts.append(f"Page {self._page}/{self._total_pages} ({self._total_ideas} ideas)")

        if self._search_query:
            parts.append(f"/{self._search_query}")

        self.update("  ".join(parts))
