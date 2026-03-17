import math

from textual.widgets import DataTable

from anne.models import Idea, IdeaStatus

_PREVIEW_LEN = 50


def _preview_text(idea: Idea) -> str:
    text = idea.reviewed_quote or idea.raw_quote or idea.raw_note or ""
    if len(text) > _PREVIEW_LEN:
        return text[:_PREVIEW_LEN] + "..."
    return text


class IdeaList(DataTable):
    DEFAULT_CSS = """
    IdeaList {
        height: 1fr;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(cursor_type="row", **kwargs)
        self._ideas: list[Idea] = []
        self._page = 1
        self._per_page = 25
        self._total = 0
        self._status_filter: IdeaStatus | None = None
        self._search_query: str = ""

    @property
    def ideas(self) -> list[Idea]:
        return self._ideas

    @property
    def page(self) -> int:
        return self._page

    @page.setter
    def page(self, value: int) -> None:
        self._page = value

    @property
    def per_page(self) -> int:
        return self._per_page

    @property
    def total(self) -> int:
        return self._total

    @total.setter
    def total(self, value: int) -> None:
        self._total = value

    @property
    def total_pages(self) -> int:
        if self._total == 0:
            return 1
        return math.ceil(self._total / self._per_page)

    @property
    def status_filter(self) -> IdeaStatus | None:
        return self._status_filter

    @status_filter.setter
    def status_filter(self, value: IdeaStatus | None) -> None:
        self._status_filter = value
        self._page = 1  # Reset to first page when filter changes

    @property
    def search_query(self) -> str:
        return self._search_query

    @search_query.setter
    def search_query(self, value: str) -> None:
        self._search_query = value
        self._page = 1  # Reset to first page when search changes

    def on_mount(self) -> None:
        self.add_columns("#", "Status", "Preview")

    def populate(self, ideas: list[Idea], total: int) -> None:
        self._ideas = ideas
        self._total = total
        self.clear()
        for idea in ideas:
            self.add_row(
                str(idea.id),
                idea.status.value,
                _preview_text(idea),
                key=str(idea.id),
            )

    def get_selected_idea(self) -> Idea | None:
        if not self._ideas or self.row_count == 0:
            return None
        cursor = self.cursor_row
        if 0 <= cursor < len(self._ideas):
            return self._ideas[cursor]
        return None

    def select_idea_by_id(self, idea_id: int) -> None:
        for i, idea in enumerate(self._ideas):
            if idea.id == idea_id:
                self.move_cursor(row=i)
                return
