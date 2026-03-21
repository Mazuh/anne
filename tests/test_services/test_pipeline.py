from dataclasses import dataclass
from unittest.mock import patch

import pytest

from anne.models import Idea, IdeaStatus
from anne.services.ideas import get_idea, insert_ideas
from anne.services.llm import ContentTooLargeError, RateLimitError, TriageDecision, ReviewResult, CaptionResult
from anne.services.parsers import ParsedIdea
from anne.services.pipeline import (
    caption_book_ideas,
    caption_single_idea,
    format_llm_error,
    review_book_ideas,
    review_single_idea,
    triage_book_ideas,
    triage_single_idea,
)
from anne.models import SourceType
from anne.services.books import create_book
from anne.services.sources import import_source


@pytest.fixture
def seeded_db(tmp_db):
    """DB with a book, source, and 3 parsed ideas."""
    book = create_book(tmp_db, "Test Book", "Test Author")
    source = import_source(tmp_db, book.id, SourceType.kindle_export_html, "notes.html", "abc123")
    ideas = [
        ParsedIdea(raw_quote=f"Quote {i}", raw_note=f"Note {i}", raw_ref=f"Ch.{i}")
        for i in range(1, 4)
    ]
    insert_ideas(tmp_db, book.id, source.id, ideas)
    return tmp_db, book


class TestTriageBookIdeas:
    def test_triages_and_rejects(self, seeded_db):
        conn, book = seeded_db
        ideas = [get_idea(conn, i) for i in range(1, 4)]

        mock_decisions = [
            TriageDecision(idea_id=1, decision="triage"),
            TriageDecision(idea_id=2, decision="reject", rejection_reason="Not relevant"),
            TriageDecision(idea_id=3, decision="triage"),
        ]

        with patch("anne.services.pipeline.triage_ideas_with_llm", return_value=mock_decisions):
            total = triage_book_ideas(
                conn,
                api_key="fake-key",
                book_title=book.title,
                book_author=book.author,
                ideas=ideas,
                chunk_size=10,
                max_input_tokens=7500,
                llm_call_interval=0,
            )

        assert total == 3
        assert get_idea(conn, 1).status == IdeaStatus.triaged
        assert get_idea(conn, 2).status == IdeaStatus.rejected
        assert get_idea(conn, 3).status == IdeaStatus.triaged

    def test_chunks_ideas(self, seeded_db):
        conn, book = seeded_db
        ideas = [get_idea(conn, i) for i in range(1, 4)]

        call_count = 0

        def mock_triage(**kwargs):
            nonlocal call_count
            call_count += 1
            return [
                TriageDecision(idea_id=idea.id, decision="triage")
                for idea in kwargs["ideas"]
            ]

        with patch("anne.services.pipeline.triage_ideas_with_llm", side_effect=mock_triage):
            total = triage_book_ideas(
                conn,
                api_key="fake-key",
                book_title=book.title,
                book_author=book.author,
                ideas=ideas,
                chunk_size=2,
                max_input_tokens=7500,
                llm_call_interval=0,
            )

        assert total == 3
        assert call_count == 2  # 2 ideas + 1 idea


class TestReviewBookIdeas:
    def test_reviews_triaged_ideas(self, seeded_db):
        conn, book = seeded_db
        # First triage the ideas
        from anne.services.ideas import triage_approve_idea
        for i in range(1, 4):
            triage_approve_idea(conn, i)
        conn.commit()

        ideas = [get_idea(conn, i) for i in range(1, 4)]

        mock_results = [
            ReviewResult(idea_id=i, reviewed_quote=f"Reviewed {i}", reviewed_comment=f"Comment {i}")
            for i in range(1, 4)
        ]

        with patch("anne.services.pipeline.review_ideas_with_llm", return_value=mock_results):
            total = review_book_ideas(
                conn,
                api_key="fake-key",
                book_title=book.title,
                book_author=book.author,
                ideas=ideas,
                chunk_size=10,
                max_input_tokens=7500,
                llm_call_interval=0,
                content_language="pt-BR",
                quote_target_length=80,
            )

        assert total == 3
        for i in range(1, 4):
            idea = get_idea(conn, i)
            assert idea.status == IdeaStatus.reviewed
            assert idea.reviewed_quote == f"Reviewed {i}"


class TestCaptionBookIdeas:
    def test_captions_reviewed_ideas(self, seeded_db):
        conn, book = seeded_db
        # Triage then review
        from anne.services.ideas import triage_approve_idea, review_idea
        for i in range(1, 4):
            triage_approve_idea(conn, i)
        conn.commit()
        for i in range(1, 4):
            review_idea(conn, i, f"Reviewed {i}", f"Comment {i}")
        conn.commit()

        ideas = [get_idea(conn, i) for i in range(1, 4)]

        mock_results = [
            CaptionResult(idea_id=i, presentation_text=f"Caption {i}", tags=["tag1", "tag2"])
            for i in range(1, 4)
        ]

        with patch("anne.services.pipeline.caption_ideas_with_llm", return_value=mock_results):
            total = caption_book_ideas(
                conn,
                api_key="fake-key",
                book_title=book.title,
                book_author=book.author,
                ideas=ideas,
                chunk_size=10,
                max_input_tokens=7500,
                llm_call_interval=0,
                content_language="pt-BR",
                cta_link="https://example.com",
            )

        assert total == 3
        for i in range(1, 4):
            idea = get_idea(conn, i)
            assert idea.status == IdeaStatus.ready
            assert idea.presentation_text == f"Caption {i}"


class TestTriageSingleIdea:
    def test_triages_parsed_idea(self, seeded_db):
        conn, book = seeded_db

        mock_decisions = [TriageDecision(idea_id=1, decision="triage")]
        with patch("anne.services.pipeline.triage_ideas_with_llm", return_value=mock_decisions):
            outcome = triage_single_idea(
                conn,
                api_key="fake-key",
                book_title=book.title,
                book_author=book.author,
                idea_id=1,
                max_input_tokens=7500,
                llm_call_interval=0,
            )

        assert outcome == "triaged"
        assert get_idea(conn, 1).status == IdeaStatus.triaged

    def test_rejects_parsed_idea(self, seeded_db):
        conn, book = seeded_db

        mock_decisions = [TriageDecision(idea_id=1, decision="reject", rejection_reason="bad")]
        with patch("anne.services.pipeline.triage_ideas_with_llm", return_value=mock_decisions):
            outcome = triage_single_idea(
                conn,
                api_key="fake-key",
                book_title=book.title,
                book_author=book.author,
                idea_id=1,
                max_input_tokens=7500,
                llm_call_interval=0,
            )

        assert outcome == "rejected"
        assert get_idea(conn, 1).status == IdeaStatus.rejected

    def test_raises_on_wrong_status(self, seeded_db):
        conn, book = seeded_db
        from anne.services.ideas import triage_approve_idea
        triage_approve_idea(conn, 1)
        conn.commit()

        with pytest.raises(ValueError, match="no longer in parsed status"):
            triage_single_idea(
                conn,
                api_key="fake-key",
                book_title=book.title,
                book_author=book.author,
                idea_id=1,
                max_input_tokens=7500,
                llm_call_interval=0,
            )

    def test_raises_on_nonexistent_idea(self, seeded_db):
        conn, book = seeded_db

        with pytest.raises(ValueError, match="no longer in parsed status"):
            triage_single_idea(
                conn,
                api_key="fake-key",
                book_title=book.title,
                book_author=book.author,
                idea_id=999,
                max_input_tokens=7500,
                llm_call_interval=0,
            )


class TestReviewSingleIdea:
    def test_reviews_triaged_idea(self, seeded_db):
        conn, book = seeded_db
        from anne.services.ideas import triage_approve_idea
        triage_approve_idea(conn, 1)
        conn.commit()

        mock_results = [ReviewResult(idea_id=1, reviewed_quote="Better quote", reviewed_comment="Context")]
        with patch("anne.services.pipeline.review_ideas_with_llm", return_value=mock_results):
            review_single_idea(
                conn,
                api_key="fake-key",
                book_title=book.title,
                book_author=book.author,
                idea_id=1,
                max_input_tokens=7500,
                llm_call_interval=0,
                content_language="pt-BR",
                quote_target_length=80,
            )

        assert get_idea(conn, 1).status == IdeaStatus.reviewed

    def test_raises_on_wrong_status(self, seeded_db):
        conn, book = seeded_db

        with pytest.raises(ValueError, match="no longer in triaged status"):
            review_single_idea(
                conn,
                api_key="fake-key",
                book_title=book.title,
                book_author=book.author,
                idea_id=1,
                max_input_tokens=7500,
                llm_call_interval=0,
                content_language="pt-BR",
                quote_target_length=80,
            )


class TestCaptionSingleIdea:
    def test_captions_reviewed_idea(self, seeded_db):
        conn, book = seeded_db
        from anne.services.ideas import triage_approve_idea, review_idea
        triage_approve_idea(conn, 1)
        conn.commit()
        review_idea(conn, 1, "Reviewed", "Comment")
        conn.commit()

        mock_results = [CaptionResult(idea_id=1, presentation_text="Caption text", tags=["a"])]
        with patch("anne.services.pipeline.caption_ideas_with_llm", return_value=mock_results):
            caption_single_idea(
                conn,
                api_key="fake-key",
                book_title=book.title,
                book_author=book.author,
                idea_id=1,
                max_input_tokens=7500,
                llm_call_interval=0,
                content_language="pt-BR",
                cta_link="https://example.com",
            )

        assert get_idea(conn, 1).status == IdeaStatus.ready

    def test_raises_on_wrong_status(self, seeded_db):
        conn, book = seeded_db

        with pytest.raises(ValueError, match="no longer in reviewed status"):
            caption_single_idea(
                conn,
                api_key="fake-key",
                book_title=book.title,
                book_author=book.author,
                idea_id=1,
                max_input_tokens=7500,
                llm_call_interval=0,
                content_language="pt-BR",
                cta_link="https://example.com",
            )


class TestFormatLlmError:
    def test_rate_limit(self):
        assert format_llm_error(RateLimitError()) == "Rate limited by Gemini API. Wait and retry."

    def test_content_too_large(self):
        assert format_llm_error(ContentTooLargeError("too big")) == "too big"

    def test_value_error(self):
        assert format_llm_error(ValueError("bad input")) == "bad input"

    def test_generic_error(self):
        assert format_llm_error(RuntimeError("oops")) == "Error: oops"
