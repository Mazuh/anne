import json
from unittest.mock import patch, MagicMock

import pytest

import anne.services.llm as llm_module
from anne.services.llm import generate, parse_essay_with_llm, RateLimitError


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
