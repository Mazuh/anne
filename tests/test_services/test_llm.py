import json
from unittest.mock import patch, MagicMock

import pytest

import anne.services.llm as llm_module
from anne.models import Idea, IdeaStatus
from anne.services.llm import generate, parse_essay_with_llm, triage_ideas_with_llm, review_ideas_with_llm, caption_ideas_with_llm, digest_notes_with_llm, synthesize_digest_with_llm, ContentTooLargeError, RateLimitError, TruncatedResponseError, _parse_json_array, _repair_truncated_json_array


@pytest.fixture(autouse=True)
def _reset_throttle():
    llm_module._last_call_time = 0


def _mock_urlopen(response_body: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _gemini_response(text: str) -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": text}]}}
        ]
    }


def test_generate_returns_text():
    body = _gemini_response("Hello, world!")
    mock = _mock_urlopen(body)
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        result = generate("fake-key", "Say hello")
    assert result == "Hello, world!"


def test_generate_bad_structure():
    mock = _mock_urlopen({"candidates": []})
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        with pytest.raises(ValueError, match="Unexpected Gemini response"):
            generate("fake-key", "prompt")


def test_parse_essay_with_llm():
    ideas_json = json.dumps([
        {"raw_quote": "To be or not to be", "raw_note": "Famous soliloquy", "raw_ref": "Act 3"},
        {"raw_quote": None, "raw_note": "Great theme of existentialism", "raw_ref": None},
    ])
    body = _gemini_response(ideas_json)
    mock = _mock_urlopen(body)
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        ideas = parse_essay_with_llm("fake-key", "Essay about Hamlet...")
    assert len(ideas) == 2
    assert ideas[0].raw_quote == "To be or not to be"
    assert ideas[0].raw_note == "Famous soliloquy"
    assert ideas[0].raw_ref == "Act 3"
    assert ideas[1].raw_quote is None
    assert ideas[1].raw_note == "Great theme of existentialism"


def test_parse_essay_skips_empty_ideas():
    ideas_json = json.dumps([
        {"raw_quote": "A real quote", "raw_note": None, "raw_ref": None},
        {"raw_quote": None, "raw_note": None, "raw_ref": "Chapter 1"},
    ])
    body = _gemini_response(ideas_json)
    mock = _mock_urlopen(body)
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        ideas = parse_essay_with_llm("fake-key", "Some essay")
    assert len(ideas) == 1
    assert ideas[0].raw_quote == "A real quote"


def test_parse_essay_handles_markdown_fenced_json():
    ideas_json = '```json\n[{"raw_quote": "Quote", "raw_note": null, "raw_ref": null}]\n```'
    body = _gemini_response(ideas_json)
    mock = _mock_urlopen(body)
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        ideas = parse_essay_with_llm("fake-key", "Essay text")
    assert len(ideas) == 1
    assert ideas[0].raw_quote == "Quote"


def test_parse_essay_malformed_json():
    body = _gemini_response("This is not JSON at all")
    mock = _mock_urlopen(body)
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        with pytest.raises(ValueError, match="Could not parse"):
            parse_essay_with_llm("fake-key", "Essay")


def test_parse_json_array_strips_markdown_fences():
    text = '```json\n[{"id": 1}]\n```'
    assert _parse_json_array(text, "test") == [{"id": 1}]


def test_parse_json_array_repairs_truncated_response():
    text = '```json\n[{"id": 1, "val": "a"}, {"id": 2, "val": "b"}, {"id": 3, "va'
    result = _parse_json_array(text, "test")
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 2


def test_repair_truncated_json_array_returns_none_for_no_objects():
    assert _repair_truncated_json_array("[") is None
    assert _repair_truncated_json_array("") is None


def test_repair_truncated_json_array_single_complete_object():
    result = _repair_truncated_json_array('[{"id": 1}, {"id":')
    assert result == [{"id": 1}]


def test_parse_json_array_raises_truncated_error_when_no_complete_objects():
    """When the response is truncated inside the first object, raise TruncatedResponseError."""
    text = '```json\n[{"id": 319, "reviewed_quote": "some quote", "reviewed_comment": "cut off mid-sen'
    with pytest.raises(TruncatedResponseError, match="truncated with no complete items"):
        _parse_json_array(text, "review")


def _make_idea(idea_id: int, raw_quote: str = "quote", raw_note: str | None = None) -> Idea:
    return Idea(
        id=idea_id, book_id=1, source_id=1, status=IdeaStatus.parsed,
        raw_quote=raw_quote, raw_note=raw_note,
        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    )


def test_triage_ideas_with_llm_mixed():
    ideas = [_make_idea(1, raw_quote="A real insight"), _make_idea(2, raw_quote="ephemeral")]
    response = json.dumps([
        {"id": 1, "decision": "triage"},
        {"id": 2, "decision": "reject", "rejection_reason": "vocab lookup"},
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        decisions = triage_ideas_with_llm("fake-key", "Book", "Author", ideas)
    assert len(decisions) == 2
    assert decisions[0].idea_id == 1
    assert decisions[0].decision == "triage"
    assert decisions[0].rejection_reason is None
    assert decisions[1].idea_id == 2
    assert decisions[1].decision == "reject"
    assert decisions[1].rejection_reason == "vocab lookup"


def test_triage_ideas_with_llm_markdown_fenced():
    ideas = [_make_idea(10, raw_quote="Some quote")]
    response = '```json\n[{"id": 10, "decision": "triage"}]\n```'
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        decisions = triage_ideas_with_llm("fake-key", "Book", "Author", ideas)
    assert len(decisions) == 1
    assert decisions[0].decision == "triage"


def test_triage_ideas_with_llm_unknown_id_skipped():
    ideas = [_make_idea(1)]
    response = json.dumps([
        {"id": 1, "decision": "triage"},
        {"id": 999, "decision": "reject", "rejection_reason": "unknown"},
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        decisions = triage_ideas_with_llm("fake-key", "Book", "Author", ideas)
    assert len(decisions) == 1
    assert decisions[0].idea_id == 1


def test_triage_ideas_with_llm_invalid_decision_defaults_to_approve():
    ideas = [_make_idea(1), _make_idea(2)]
    response = json.dumps([
        {"id": 1, "decision": "triage"},
        {"id": 2, "decision": "maybe"},
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        decisions = triage_ideas_with_llm("fake-key", "Book", "Author", ideas)
    # idea 2 had invalid decision, so it's treated as omitted → default triage
    assert len(decisions) == 2
    by_id = {d.idea_id: d for d in decisions}
    assert by_id[1].decision == "triage"
    assert by_id[2].decision == "triage"


def test_triage_ideas_with_llm_omitted_ids_default_to_approve():
    ideas = [_make_idea(1), _make_idea(2), _make_idea(3)]
    response = json.dumps([
        {"id": 1, "decision": "reject", "rejection_reason": "vocab"},
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        decisions = triage_ideas_with_llm("fake-key", "Book", "Author", ideas)
    assert len(decisions) == 3
    by_id = {d.idea_id: d for d in decisions}
    assert by_id[1].decision == "reject"
    assert by_id[2].decision == "triage"
    assert by_id[3].decision == "triage"


def test_triage_ideas_with_llm_duplicate_id_skipped():
    ideas = [_make_idea(1)]
    response = json.dumps([
        {"id": 1, "decision": "triage"},
        {"id": 1, "decision": "reject", "rejection_reason": "changed my mind"},
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        decisions = triage_ideas_with_llm("fake-key", "Book", "Author", ideas)
    assert len(decisions) == 1
    assert decisions[0].decision == "triage"


def test_triage_ideas_with_llm_content_too_large():
    ideas = [_make_idea(1, raw_quote="x" * 10000)]
    with pytest.raises(ContentTooLargeError, match="Triage prompt too large"):
        triage_ideas_with_llm("fake-key", "Book", "Author", ideas, max_input_tokens=100)


# --- review_ideas_with_llm tests ---


def _make_triaged_idea(idea_id: int, raw_quote: str = "quote", raw_note: str | None = None) -> Idea:
    return Idea(
        id=idea_id, book_id=1, source_id=1, status=IdeaStatus.triaged,
        raw_quote=raw_quote, raw_note=raw_note,
        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    )


def test_review_ideas_with_llm_happy_path():
    ideas = [_make_triaged_idea(1, raw_quote="A long original quote from the book")]
    response = json.dumps([
        {
            "id": 1,
            "reviewed_quote": "**Short** quote",
            "reviewed_comment": "The author wrote this during wartime.",
        }
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        results = review_ideas_with_llm("fake-key", "Book", "Author", ideas)
    assert len(results) == 1
    assert results[0].idea_id == 1
    assert results[0].reviewed_quote == "**Short** quote"
    assert results[0].reviewed_comment == "The author wrote this during wartime."


def test_review_ideas_with_llm_unknown_id_skipped():
    ideas = [_make_triaged_idea(1)]
    response = json.dumps([
        {"id": 1, "reviewed_quote": "Q", "reviewed_comment": "C"},
        {"id": 999, "reviewed_quote": "X", "reviewed_comment": "Y"},
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        results = review_ideas_with_llm("fake-key", "Book", "Author", ideas)
    assert len(results) == 1
    assert results[0].idea_id == 1


def test_review_ideas_with_llm_omitted_ids_not_defaulted():
    ideas = [_make_triaged_idea(1), _make_triaged_idea(2), _make_triaged_idea(3)]
    response = json.dumps([
        {"id": 1, "reviewed_quote": "Q1", "reviewed_comment": "C1"},
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        results = review_ideas_with_llm("fake-key", "Book", "Author", ideas)
    # Only idea 1 returned — ideas 2 and 3 are NOT defaulted
    assert len(results) == 1
    assert results[0].idea_id == 1


def test_review_ideas_with_llm_content_too_large():
    ideas = [_make_triaged_idea(1, raw_quote="x" * 10000)]
    with pytest.raises(ContentTooLargeError, match="Review prompt too large"):
        review_ideas_with_llm("fake-key", "Book", "Author", ideas, max_input_tokens=100)


# --- caption_ideas_with_llm tests ---


def _make_reviewed_idea(idea_id: int, reviewed_quote: str = "quote", reviewed_comment: str = "comment") -> Idea:
    return Idea(
        id=idea_id, book_id=1, source_id=1, status=IdeaStatus.reviewed,
        raw_quote="original", reviewed_quote=reviewed_quote,
        reviewed_comment=reviewed_comment,
        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    )


def test_caption_ideas_with_llm_happy_path():
    ideas = [_make_reviewed_idea(1)]
    response = json.dumps([
        {
            "id": 1,
            "presentation_text": "This hook grabs you.\n\nThe rest of the caption.",
            "tags": ["poder", "ironia"],
        }
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        results = caption_ideas_with_llm("fake-key", "Book", "Author", ideas)
    assert len(results) == 1
    assert results[0].idea_id == 1
    assert "hook" in results[0].presentation_text
    assert results[0].tags == ["poder", "ironia"]


def test_caption_ideas_with_llm_with_cta_link():
    ideas = [_make_reviewed_idea(1)]
    response = json.dumps([
        {
            "id": 1,
            "presentation_text": "Caption with link.\n\nhttps://example.com\n\n#hashtag",
            "tags": ["reflexao"],
        }
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        results = caption_ideas_with_llm(
            "fake-key", "Book", "Author", ideas, cta_link="https://example.com"
        )
    assert len(results) == 1
    assert results[0].presentation_text is not None


def test_caption_ideas_with_llm_omitted_ids_not_defaulted():
    ideas = [_make_reviewed_idea(1), _make_reviewed_idea(2)]
    response = json.dumps([
        {"id": 1, "presentation_text": "Caption 1", "tags": ["mood"]},
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        results = caption_ideas_with_llm("fake-key", "Book", "Author", ideas)
    # Only idea 1 returned — idea 2 stays reviewed (strict mode)
    assert len(results) == 1
    assert results[0].idea_id == 1


def test_caption_ideas_with_llm_content_too_large():
    ideas = [_make_reviewed_idea(1, reviewed_quote="x" * 10000)]
    with pytest.raises(ContentTooLargeError, match="Caption prompt too large"):
        caption_ideas_with_llm("fake-key", "Book", "Author", ideas, max_input_tokens=100)


# --- digest_notes_with_llm tests ---


def _make_commented_idea(idea_id: int, raw_quote: str = "quote", raw_note: str = "note", raw_ref: str | None = "Ch.1") -> Idea:
    return Idea(
        id=idea_id, book_id=1, source_id=1, status=IdeaStatus.triaged,
        raw_quote=raw_quote, raw_note=raw_note, raw_ref=raw_ref,
        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    )


def test_digest_notes_with_llm_returns_markdown():
    ideas = [
        _make_commented_idea(1, raw_quote="Power is not a means", raw_note="Key theme"),
        _make_commented_idea(2, raw_quote="War is peace", raw_note="Orwellian paradox"),
    ]
    markdown_response = "## Theme: Power\n\n- ⭐ \"Power is not a means\" — Reader: Key theme (Ch.1)\n"
    mock = _mock_urlopen(_gemini_response(markdown_response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        result = digest_notes_with_llm("fake-key", "1984", "George Orwell", ideas)
    assert "Power" in result
    assert isinstance(result, str)


def test_digest_notes_with_llm_strips_markdown_fences():
    ideas = [_make_commented_idea(1)]
    fenced = "```markdown\n## Themes\n\n- Item 1\n```"
    mock = _mock_urlopen(_gemini_response(fenced))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        result = digest_notes_with_llm("fake-key", "Book", "Author", ideas)
    assert not result.startswith("```")
    assert "Themes" in result


def test_digest_notes_with_llm_content_too_large():
    ideas = [_make_commented_idea(1, raw_quote="x" * 10000)]
    with pytest.raises(ContentTooLargeError, match="Digest prompt too large"):
        digest_notes_with_llm("fake-key", "Book", "Author", ideas, max_input_tokens=100)


def test_digest_notes_with_llm_uses_reviewed_quote_when_available():
    idea = Idea(
        id=1, book_id=1, source_id=1, status=IdeaStatus.reviewed,
        raw_quote="Long original quote from the book",
        raw_note="My comment",
        reviewed_quote="Short refined quote",
        reviewed_comment="Factual context",
        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    )
    mock = _mock_urlopen(_gemini_response("## Theme\n\n- Item"))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock) as mock_call:
        digest_notes_with_llm("fake-key", "Book", "Author", [idea])
    # Check that the prompt sent to the API includes the reviewed_quote
    call_data = json.loads(mock_call.call_args[0][0].data)
    prompt_text = call_data["contents"][0]["parts"][0]["text"]
    assert "Short refined quote" in prompt_text


def test_synthesize_digest_with_llm_merges_chunks():
    chunk1 = "## Theme A\n\n- Item 1"
    chunk2 = "## Theme B\n\n- Item 2"
    merged = "## Theme A\n\n- Item 1\n\n## Theme B\n\n- Item 2"
    mock = _mock_urlopen(_gemini_response(merged))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        result = synthesize_digest_with_llm("fake-key", "Book", "Author", [chunk1, chunk2])
    assert "Theme A" in result
    assert "Theme B" in result


def test_synthesize_digest_with_llm_content_too_large():
    chunks = ["x" * 10000]
    with pytest.raises(ContentTooLargeError, match="Synthesis prompt too large"):
        synthesize_digest_with_llm("fake-key", "Book", "Author", chunks, max_input_tokens=100)
