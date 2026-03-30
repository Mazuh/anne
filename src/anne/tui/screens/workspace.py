from __future__ import annotations

import os
import subprocess
import tempfile
from typing import TYPE_CHECKING

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input
from textual.worker import Worker, get_current_worker

if TYPE_CHECKING:
    from anne.tui.modals.loading import LoadingModal

from anne.models import Book, Idea, IdeaStatus
from anne.tui.widgets.action_panel import ActionPanel
from anne.tui.widgets.idea_detail import IdeaDetail
from anne.tui.widgets.idea_list import IdeaList
from anne.tui.widgets.status_bar import StatusBar


class BookWorkspaceScreen(Screen):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("n", "next_page", "Next page"),
        Binding("p", "prev_page", "Prev page"),
        Binding("r", "refresh", "Refresh"),
        Binding("a", "triage", "Triage", show=False),
        Binding("x", "reject", "Reject", show=False),
        Binding("u", "unreject", "Unreject", show=False),
        Binding("e", "edit_field", "Edit", show=False),
        Binding("t", "edit_tags", "Tags", show=False),
        Binding("E", "open_editor", "Editor", show=False),
        Binding("f", "filter_status", "Filter"),
        Binding("T", "filter_tag", "Tag filter"),
        Binding("P", "publish", "Publish", show=False),
        Binding("c", "copy_field", "Copy", show=False),
        Binding("question_mark", "ai_prompt", "AI prompt", show=False),
        Binding("A", "action_menu", "Actions"),
        Binding("slash", "search", "Search"),
        Binding("q", "go_back", "Back"),
    ]

    def __init__(self, book: Book) -> None:
        super().__init__()
        self._book = book
        self._source_paths: dict[int, str] = {}
        self._llm_in_progress: bool = False
        self._loading_modal: LoadingModal | None = None
        self._ai_worker: Worker | None = None
        self._current_prompt_idea: Idea | None = None
        self._current_prompt_text: str = ""

    def on_mount(self) -> None:
        self.sub_title = self._book.title
        search_input = self.query_one("#search-input", Input)
        search_input.display = False
        self._load_ideas()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace-layout"):
            yield IdeaList(id="idea-list")
            yield IdeaDetail(id="idea-detail")
            yield ActionPanel(id="action-panel")
        yield StatusBar(id="status-bar")
        yield Input(placeholder="Search...", id="search-input")
        yield Footer()

    @work(thread=True)
    def _load_ideas(self, select_idea_id: int | None = None) -> None:
        from anne.db.connection import get_connection
        from anne.services.ideas import count_ideas, list_ideas_paginated
        from anne.services.sources import list_sources

        idea_list = self.query_one("#idea-list", IdeaList)
        settings = self.app.settings

        with get_connection(settings.db_path) as conn:
            if not self._source_paths:
                sources = list_sources(conn, self._book.id)
                self._source_paths = {s.id: s.path for s in sources}

            status_filter = idea_list.status_filter
            tag_filter = idea_list.tag_filter
            search = idea_list.search_query or None

            total = count_ideas(
                conn, book_id=self._book.id, status=status_filter, search=search,
                tag=tag_filter,
            )
            ideas = list_ideas_paginated(
                conn,
                book_id=self._book.id,
                status=status_filter,
                page=idea_list.page,
                per_page=idea_list.per_page,
                search=search,
                tag=tag_filter,
            )

        self.app.call_from_thread(self._populate, ideas, total, select_idea_id)

    def _populate(self, ideas: list[Idea], total: int, select_idea_id: int | None = None) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea_list.populate(ideas, total)

        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.refresh_bar(
            status_filter=idea_list.status_filter,
            page=idea_list.page,
            total_pages=idea_list.total_pages,
            total_ideas=total,
            search_query=idea_list.search_query,
            tag_filter=idea_list.tag_filter,
        )

        if select_idea_id is not None:
            idea_list.select_idea_by_id(select_idea_id)
        elif ideas:
            self._show_idea_detail(ideas[0])

    @on(DataTable.RowHighlighted, "#idea-list")
    def _on_idea_cursor_changed(self, event: DataTable.RowHighlighted) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea = idea_list.get_selected_idea()
        if idea:
            self._show_idea_detail(idea)

    def _show_idea_detail(self, idea: Idea) -> None:
        detail = self.query_one("#idea-detail", IdeaDetail)
        source_path = self._source_paths.get(idea.source_id, "?")
        detail.show_idea(idea, self._book.title, source_path)

        action_panel = self.query_one("#action-panel", ActionPanel)
        action_panel.update_for_idea(idea)

    # Navigation
    def action_cursor_down(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea_list.action_cursor_down()

    def action_cursor_up(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea_list.action_cursor_up()

    def action_next_page(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        if idea_list.page < idea_list.total_pages:
            idea_list.page += 1
            self._load_ideas()

    def action_prev_page(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        if idea_list.page > 1:
            idea_list.page -= 1
            self._load_ideas()

    def action_refresh(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        selected = idea_list.get_selected_idea()
        self._load_ideas(select_idea_id=selected.id if selected else None)

    def action_go_back(self) -> None:
        self.app.pop_screen()

    # Mutations
    def action_triage(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea = idea_list.get_selected_idea()
        if idea and idea.status == IdeaStatus.parsed:
            self._do_triage(idea.id)

    @work(thread=True)
    def _do_triage(self, idea_id: int) -> None:
        from anne.db.connection import get_connection
        from anne.services.ideas import triage_approve_idea

        try:
            with get_connection(self.app.settings.db_path) as conn:
                triage_approve_idea(conn, idea_id)
            self.app.call_from_thread(self.notify, f"Idea {idea_id} triaged.")
            self._load_ideas(select_idea_id=idea_id)
        except ValueError as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")

    def action_reject(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea = idea_list.get_selected_idea()
        if not idea:
            return
        allowed = {IdeaStatus.parsed, IdeaStatus.triaged, IdeaStatus.reviewed, IdeaStatus.ready}
        if idea.status not in allowed:
            self.notify("Cannot reject from this status.", severity="warning")
            return
        from anne.tui.modals.confirm import ConfirmModal
        preview = (idea.raw_quote or idea.raw_note or "")[:80]
        self.app.push_screen(
            ConfirmModal(f'Reject idea #{idea.id}?\n"{preview}"', show_reason=True),
            callback=lambda result: self._on_reject_confirmed(idea.id, result),
        )

    def _on_reject_confirmed(self, idea_id: int, result: tuple[bool, str]) -> None:
        confirmed, reason = result
        if confirmed:
            self._do_reject(idea_id, reason or None)

    @work(thread=True)
    def _do_reject(self, idea_id: int, reason: str | None) -> None:
        from anne.db.connection import get_connection
        from anne.services.ideas import update_idea

        try:
            # Uses update_idea(force=True) instead of reject_idea() because
            # the TUI allows rejecting from triaged/reviewed, not just parsed.
            with get_connection(self.app.settings.db_path) as conn:
                fields: dict[str, str] = {"status": IdeaStatus.rejected.value}
                if reason:
                    fields["rejection_reason"] = reason
                update_idea(conn, idea_id, force=True, **fields)
            self.app.call_from_thread(self.notify, f"Idea {idea_id} rejected.")
            self._load_ideas(select_idea_id=idea_id)
        except ValueError as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")

    def action_unreject(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea = idea_list.get_selected_idea()
        if idea and idea.status == IdeaStatus.rejected:
            self._do_unreject(idea.id)

    @work(thread=True)
    def _do_unreject(self, idea_id: int) -> None:
        from anne.db.connection import get_connection
        from anne.services.ideas import update_idea

        try:
            with get_connection(self.app.settings.db_path) as conn:
                update_idea(conn, idea_id, force=True, status=IdeaStatus.parsed.value)
            self.app.call_from_thread(self.notify, f"Idea {idea_id} unrejected → parsed.")
            self._load_ideas(select_idea_id=idea_id)
        except ValueError as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")

    def action_publish(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea = idea_list.get_selected_idea()
        if not idea:
            return
        if idea.status != IdeaStatus.ready:
            self.notify("Only ready ideas can be published.", severity="warning")
            return
        from anne.tui.modals.confirm import ConfirmModal
        text = idea.presentation_text or idea.reviewed_quote or idea.raw_quote or ""
        preview = text[:80] + "…" if len(text) > 80 else text
        self.app.push_screen(
            ConfirmModal(f'Mark idea #{idea.id} as published?\n"{preview}"'),
            callback=lambda result: self._on_publish_confirmed(idea.id, result),
        )

    def _on_publish_confirmed(self, idea_id: int, result: tuple[bool, str]) -> None:
        confirmed, _ = result
        if confirmed:
            self._do_publish(idea_id)

    @work(thread=True)
    def _do_publish(self, idea_id: int) -> None:
        from anne.db.connection import get_connection
        from anne.services.ideas import publish_idea

        try:
            with get_connection(self.app.settings.db_path) as conn:
                publish_idea(conn, idea_id)
            self.app.call_from_thread(self.notify, f"Idea {idea_id} published!")
            self._load_ideas(select_idea_id=idea_id)
        except ValueError as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")

    # Filter & Search
    def action_filter_status(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        from anne.tui.modals.filter import FilterModal
        self.app.push_screen(
            FilterModal(idea_list.status_filter),
            callback=self._on_filter_selected,
        )

    def _on_filter_selected(self, status: IdeaStatus | None) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea_list.status_filter = status
        self._load_ideas()

    def action_filter_tag(self) -> None:
        self._fetch_tags_for_filter()

    @work(thread=True)
    def _fetch_tags_for_filter(self) -> None:
        from anne.db.connection import get_connection
        from anne.services.ideas import get_distinct_tags

        with get_connection(self.app.settings.db_path) as conn:
            tags = get_distinct_tags(conn, self._book.id)

        idea_list = self.query_one("#idea-list", IdeaList)
        current_tag = idea_list.tag_filter
        self.app.call_from_thread(self._open_tag_filter_modal, current_tag, tags)

    def _open_tag_filter_modal(self, current_tag: str | None, tags: list[str]) -> None:
        from anne.tui.modals.tag_filter import TagFilterModal
        self.app.push_screen(
            TagFilterModal(current_tag, tags),
            callback=self._on_tag_filter_selected,
        )

    def _on_tag_filter_selected(self, tag: str | None) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea_list.tag_filter = tag
        self._load_ideas()

    def action_search(self) -> None:
        search_input = self.query_one("#search-input", Input)
        search_input.display = True
        search_input.focus()

    @on(Input.Submitted, "#search-input")
    def _on_search_submitted(self, event: Input.Submitted) -> None:
        search_input = self.query_one("#search-input", Input)
        idea_list = self.query_one("#idea-list", IdeaList)
        idea_list.search_query = search_input.value.strip()
        search_input.display = False
        idea_list.focus()
        self._load_ideas()

    # Edit
    def action_edit_field(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea = idea_list.get_selected_idea()
        if not idea:
            return
        from anne.tui.modals.edit_field import EditFieldModal
        self.app.push_screen(
            EditFieldModal(idea),
            callback=lambda result: self._on_edit_result(idea.id, result),
        )

    def action_edit_tags(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea = idea_list.get_selected_idea()
        if not idea:
            return
        from anne.tui.modals.edit_field import EditFieldModal
        self.app.push_screen(
            EditFieldModal(idea, preset_field="tags"),
            callback=lambda result: self._on_edit_result(idea.id, result),
        )

    def _on_edit_result(self, idea_id: int, result: tuple[str, str] | None) -> None:
        if result is not None:
            field, value = result
            self._do_edit(idea_id, field, value)

    @work(thread=True)
    def _do_edit(self, idea_id: int, field: str, value: str) -> None:
        from anne.db.connection import get_connection
        from anne.services.ideas import update_idea

        try:
            with get_connection(self.app.settings.db_path) as conn:
                update_idea(conn, idea_id, force=True, **{field: value})
            self.app.call_from_thread(self.notify, f"Idea {idea_id}: {field} updated.")
            self._load_ideas(select_idea_id=idea_id)
        except ValueError as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")

    def action_open_editor(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea = idea_list.get_selected_idea()
        if not idea:
            return

        editor = os.environ.get("EDITOR", "vi")
        field = "reviewed_quote" if idea.reviewed_quote is not None else "raw_quote"
        current = getattr(idea, field) or ""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="anne_idea_"
        ) as f:
            f.write(current)
            tmp_path = f.name

        idea_id = idea.id

        try:
            with self.app.suspend():
                result = subprocess.run([editor, tmp_path])
        except FileNotFoundError:
            os.unlink(tmp_path)
            self.notify(f"Editor '{editor}' not found.", severity="error")
            return

        if result.returncode != 0:
            os.unlink(tmp_path)
            self.notify(f"Editor exited with code {result.returncode}.", severity="error")
            return

        try:
            with open(tmp_path) as f:
                new_value = f.read()
        finally:
            os.unlink(tmp_path)

        if new_value != current:
            self._do_edit(idea_id, field, new_value)

    # Copy field to clipboard (macOS only, uses pbcopy)
    def action_copy_field(self) -> None:
        import sys

        if sys.platform != "darwin":
            self.notify("Copy to clipboard requires macOS.", severity="error")
            return
        idea_list = self.query_one("#idea-list", IdeaList)
        idea = idea_list.get_selected_idea()
        if not idea:
            return
        from anne.tui.modals.copy_field import CopyFieldModal
        self.app.push_screen(
            CopyFieldModal(idea),
            callback=self._on_copy_field_selected,
        )

    def _on_copy_field_selected(self, field_name: str | None) -> None:
        if field_name is None:
            return
        idea_list = self.query_one("#idea-list", IdeaList)
        idea = idea_list.get_selected_idea()
        if not idea:
            return
        value = getattr(idea, field_name, "") or ""
        if field_name == "tags":
            import json

            try:
                tags_list = json.loads(value)
                value = ", ".join(tags_list) if isinstance(tags_list, list) else value
            except (json.JSONDecodeError, TypeError):
                pass
        try:
            subprocess.run(
                ["pbcopy"],
                input=value.encode(),
                check=True,
            )
            self.notify(f"Copied {field_name.replace('_', ' ')} to clipboard.")
        except (FileNotFoundError, subprocess.CalledProcessError):
            self.notify("Failed to copy to clipboard.", severity="error")

    # AI prompt (custom LLM prompt for ready/published ideas)
    def action_ai_prompt(self) -> None:
        if self._llm_in_progress:
            self.notify("LLM call already in progress.", severity="warning")
            return
        idea_list = self.query_one("#idea-list", IdeaList)
        idea = idea_list.get_selected_idea()
        if not idea:
            return
        if idea.status not in (IdeaStatus.ready, IdeaStatus.published):
            self.notify(
                "AI prompt is only available for ready or published ideas.",
                severity="warning",
            )
            return
        if not idea.reviewed_quote or not idea.presentation_text:
            self.notify("Idea is missing reviewed quote or caption.", severity="warning")
            return
        from anne.tui.modals.custom_prompt import CustomPromptModal

        self.app.push_screen(
            CustomPromptModal(),
            callback=lambda prompt_text: self._on_custom_prompt(idea, prompt_text),
        )

    def _on_custom_prompt(self, idea: Idea, prompt_text: str | None) -> None:
        if prompt_text:
            self._current_prompt_idea = idea
            self._current_prompt_text = prompt_text
            self._llm_in_progress = True
            from anne.tui.modals.loading import LoadingModal

            self._loading_modal = LoadingModal()
            self.app.push_screen(
                self._loading_modal,
                callback=self._on_loading_dismissed,
            )
            self._ai_worker = self._do_ai_prompt(idea, prompt_text)

    def _on_loading_dismissed(self, completed: bool) -> None:
        if not completed:
            self._llm_in_progress = False
            if self._ai_worker and not self._ai_worker.is_finished:
                self._ai_worker.cancel()
            self._ai_worker = None
            self._loading_modal = None
            self.notify("LLM call cancelled.")

    @work(thread=True)
    def _do_ai_prompt(self, idea: Idea, prompt_text: str) -> None:
        from anne.services.llm import custom_prompt_idea
        from anne.services.pipeline import format_llm_error
        worker = get_current_worker()
        settings = self.app.settings
        api_key = settings.gemini_api_key
        if not api_key:
            if worker.is_cancelled:
                return
            self.app.call_from_thread(self._dismiss_loading)
            self.app.call_from_thread(self.notify, "Gemini API key not configured", severity="error")
            return

        try:
            response = custom_prompt_idea(
                api_key=api_key,
                reviewed_quote=idea.reviewed_quote,
                presentation_text=idea.presentation_text,
                prompt_text=prompt_text,
                content_language=settings.content_language,
                min_interval=settings.llm_call_interval,
            )
            if worker.is_cancelled:
                return
            self.app.call_from_thread(self._dismiss_loading_and_show_response, response, prompt_text)
        except Exception as e:
            if worker.is_cancelled:
                return
            self.app.call_from_thread(self._dismiss_loading)
            self.app.call_from_thread(self.notify, format_llm_error(e), severity="error")

    def _dismiss_loading(self) -> None:
        if self._loading_modal is None:
            return
        self._llm_in_progress = False
        modal = self._loading_modal
        self._loading_modal = None
        self._ai_worker = None
        if modal and modal.is_attached:
            modal.dismiss(False)

    def _dismiss_loading_and_show_response(self, response: str, prompt_text: str) -> None:
        self._dismiss_loading()
        self._show_prompt_response(response, prompt_text)

    def _show_prompt_response(self, response: str, prompt_text: str) -> None:
        from anne.tui.modals.prompt_response import PromptResponseModal

        self.app.push_screen(
            PromptResponseModal(response, prompt=prompt_text),
            callback=self._on_prompt_response,
        )

    def _on_prompt_response(self, result: bool | None) -> None:
        idea = self._current_prompt_idea
        prompt = self._current_prompt_text
        self._current_prompt_idea = None
        self._current_prompt_text = ""
        if result is True and idea is not None:
            from anne.tui.modals.custom_prompt import CustomPromptModal

            self.app.push_screen(
                CustomPromptModal(initial_prompt=prompt),
                callback=lambda prompt_text, _idea=idea: self._on_custom_prompt(
                    _idea, prompt_text
                ),
            )

    # Action menu (LLM pipeline per-idea)
    _LLM_ACTION_FOR_STATUS: dict[str, str] = {
        "parsed": "Triage with LLM",
        "triaged": "Review with LLM",
        "reviewed": "Caption with LLM",
    }

    _LLM_ACTION_DESCRIPTIONS: dict[str, str] = {
        "Triage with LLM": "Use LLM to approve or reject this idea",
        "Review with LLM": "Refine quote and add context with LLM",
        "Caption with LLM": "Generate Instagram caption with LLM",
    }

    def action_action_menu(self) -> None:
        idea_list = self.query_one("#idea-list", IdeaList)
        idea = idea_list.get_selected_idea()
        if not idea:
            return

        action_label = self._LLM_ACTION_FOR_STATUS.get(idea.status)
        if not action_label:
            self.notify("No LLM actions available for this status.", severity="warning")
            return

        from anne.tui.modals.action_menu import ActionModal
        self.app.push_screen(
            ActionModal("LLM Actions", [action_label], self._LLM_ACTION_DESCRIPTIONS),
            callback=lambda result: self._on_llm_action_selected(idea.id, result),
        )

    def _on_llm_action_selected(self, idea_id: int, action: str | None) -> None:
        if action == "Triage with LLM":
            self._run_llm_triage(idea_id)
        elif action == "Review with LLM":
            self._run_llm_review(idea_id)
        elif action == "Caption with LLM":
            self._run_llm_caption(idea_id)

    @work(thread=True)
    def _run_llm_triage(self, idea_id: int) -> None:
        from anne.db.connection import get_connection
        from anne.services.pipeline import format_llm_error, triage_single_idea

        settings = self.app.settings
        api_key = settings.gemini_api_key
        if not api_key:
            self.app.call_from_thread(self.notify, "Gemini API key not configured", severity="error")
            return

        try:
            with get_connection(settings.db_path) as conn:
                outcome = triage_single_idea(
                    conn,
                    api_key=api_key,
                    book_title=self._book.title,
                    book_author=self._book.author,
                    idea_id=idea_id,
                    max_input_tokens=settings.max_llm_input_tokens,
                    llm_call_interval=settings.llm_call_interval,
                )
                self.app.call_from_thread(self.notify, f"Idea {idea_id} {outcome} by LLM.")

            self._load_ideas(select_idea_id=idea_id)
        except Exception as e:
            self.app.call_from_thread(self.notify, format_llm_error(e), severity="error")

    @work(thread=True)
    def _run_llm_review(self, idea_id: int) -> None:
        from anne.db.connection import get_connection
        from anne.services.pipeline import format_llm_error, review_single_idea

        settings = self.app.settings
        api_key = settings.gemini_api_key
        if not api_key:
            self.app.call_from_thread(self.notify, "Gemini API key not configured", severity="error")
            return

        try:
            with get_connection(settings.db_path) as conn:
                review_single_idea(
                    conn,
                    api_key=api_key,
                    book_title=self._book.title,
                    book_author=self._book.author,
                    idea_id=idea_id,
                    max_input_tokens=settings.max_llm_input_tokens,
                    llm_call_interval=settings.llm_call_interval,
                    content_language=settings.content_language,
                    quote_target_length=settings.review_quote_target_length,
                )
                self.app.call_from_thread(self.notify, f"Idea {idea_id} reviewed by LLM.")

            self._load_ideas(select_idea_id=idea_id)
        except Exception as e:
            self.app.call_from_thread(self.notify, format_llm_error(e), severity="error")

    @work(thread=True)
    def _run_llm_caption(self, idea_id: int) -> None:
        from anne.db.connection import get_connection
        from anne.services.pipeline import caption_single_idea, format_llm_error

        settings = self.app.settings
        api_key = settings.gemini_api_key
        if not api_key:
            self.app.call_from_thread(self.notify, "Gemini API key not configured", severity="error")
            return

        try:
            with get_connection(settings.db_path) as conn:
                caption_single_idea(
                    conn,
                    api_key=api_key,
                    book_title=self._book.title,
                    book_author=self._book.author,
                    idea_id=idea_id,
                    max_input_tokens=settings.max_llm_input_tokens,
                    llm_call_interval=settings.llm_call_interval,
                    content_language=settings.content_language,
                    cta_link=settings.cta_link,
                )
                self.app.call_from_thread(self.notify, f"Idea {idea_id} captioned by LLM.")

            self._load_ideas(select_idea_id=idea_id)
        except Exception as e:
            self.app.call_from_thread(self.notify, format_llm_error(e), severity="error")
