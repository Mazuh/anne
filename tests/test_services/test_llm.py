import json
from unittest.mock import patch, MagicMock

import pytest

import anne.services.llm as llm_module
from anne.models import Idea, IdeaStatus
from anne.services.llm import generate, parse_essay_with_llm, triage_ideas_with_llm, ContentTooLargeError, RateLimitError


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


def _make_idea(idea_id: int, raw_quote: str = "quote", raw_note: str | None = None) -> Idea:
    return Idea(
        id=idea_id, book_id=1, source_id=1, status=IdeaStatus.parsed,
        raw_quote=raw_quote, raw_note=raw_note,
        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    )


def test_triage_ideas_with_llm_mixed():
    ideas = [_make_idea(1, raw_quote="A real insight"), _make_idea(2, raw_quote="ephemeral")]
    response = json.dumps([
        {"id": 1, "decision": "approve"},
        {"id": 2, "decision": "reject", "rejection_reason": "vocab lookup"},
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        decisions = triage_ideas_with_llm("fake-key", "Book", "Author", ideas)
    assert len(decisions) == 2
    assert decisions[0].idea_id == 1
    assert decisions[0].decision == "approve"
    assert decisions[0].rejection_reason is None
    assert decisions[1].idea_id == 2
    assert decisions[1].decision == "reject"
    assert decisions[1].rejection_reason == "vocab lookup"


def test_triage_ideas_with_llm_markdown_fenced():
    ideas = [_make_idea(10, raw_quote="Some quote")]
    response = '```json\n[{"id": 10, "decision": "approve"}]\n```'
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        decisions = triage_ideas_with_llm("fake-key", "Book", "Author", ideas)
    assert len(decisions) == 1
    assert decisions[0].decision == "approve"


def test_triage_ideas_with_llm_unknown_id_skipped():
    ideas = [_make_idea(1)]
    response = json.dumps([
        {"id": 1, "decision": "approve"},
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
        {"id": 1, "decision": "approve"},
        {"id": 2, "decision": "maybe"},
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        decisions = triage_ideas_with_llm("fake-key", "Book", "Author", ideas)
    # idea 2 had invalid decision, so it's treated as omitted → default approve
    assert len(decisions) == 2
    by_id = {d.idea_id: d for d in decisions}
    assert by_id[1].decision == "approve"
    assert by_id[2].decision == "approve"


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
    assert by_id[2].decision == "approve"
    assert by_id[3].decision == "approve"


def test_triage_ideas_with_llm_duplicate_id_skipped():
    ideas = [_make_idea(1)]
    response = json.dumps([
        {"id": 1, "decision": "approve"},
        {"id": 1, "decision": "reject", "rejection_reason": "changed my mind"},
    ])
    mock = _mock_urlopen(_gemini_response(response))
    with patch("anne.services.llm.urllib.request.urlopen", return_value=mock):
        decisions = triage_ideas_with_llm("fake-key", "Book", "Author", ideas)
    assert len(decisions) == 1
    assert decisions[0].decision == "approve"


def test_triage_ideas_with_llm_content_too_large():
    ideas = [_make_idea(1, raw_quote="x" * 10000)]
    with pytest.raises(ContentTooLargeError, match="Triage prompt too large"):
        triage_ideas_with_llm("fake-key", "Book", "Author", ideas, max_input_tokens=100)
