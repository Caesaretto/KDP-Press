"""Tests for agents/phrase_agent.py — generate_phrases().

All OpenAI calls are mocked. No real API key is required.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agents.phrase_agent import generate_phrases
from zodiac_config import SIGN_ORDER


# ───────────────────────────── helpers ─────────────────────────────────────


def _make_mock_client(content: str) -> MagicMock:
    """Build a mock OpenAI client whose chat.completions.create returns `content`."""
    client = MagicMock()
    # Mimic the openai SDK response shape: response.choices[0].message.content
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    client.chat.completions.create.return_value = response
    return client


def _zodiac_response(n: int = 30) -> str:
    """JSON payload as the LLM would return for the astrology niche."""
    items = []
    for i in range(n):
        sign = SIGN_ORDER[i % len(SIGN_ORDER)]
        items.append({"sign": sign, "text": f"FRASE {i + 1} PER {sign.upper()}."})
    return json.dumps({"phrases": items})


def _generic_response(n: int = 30) -> str:
    """JSON payload as the LLM returns when phrases are plain strings."""
    items = [f"FRASE GENERICA {i + 1}." for i in range(n)]
    return json.dumps({"phrases": items})


# ──────────────────────────── happy paths ──────────────────────────────────


def test_astrology_happy_path_30_phrases():
    client = _make_mock_client(_zodiac_response(30))

    phrases = generate_phrases(
        book_theme="Zodiacale Esaurito",
        niche="astrology",
        count=30,
        client=client,
    )

    assert isinstance(phrases, list)
    assert len(phrases) == 30
    sign_set = set(SIGN_ORDER)
    for item in phrases:
        assert isinstance(item, dict)
        assert "text" in item and item["text"]
        assert "subject_key" in item
        assert item["subject_key"] in sign_set


def test_generic_niche_returns_subject_key_none():
    client = _make_mock_client(_generic_response(30))

    phrases = generate_phrases(
        book_theme="Office Burnout",
        niche="office_burnout",
        count=30,
        client=client,
    )

    assert len(phrases) == 30
    for item in phrases:
        assert isinstance(item, dict)
        assert item["text"]
        assert item["subject_key"] is None


# ──────────────────────────── edge cases ───────────────────────────────────


def test_too_few_phrases_raises_runtime_error():
    # Generic strings, only 5 returned when 30 requested → must raise
    short = json.dumps({"phrases": [f"FRASE {i}." for i in range(5)]})
    client = _make_mock_client(short)

    with pytest.raises(RuntimeError, match="usable phrases"):
        generate_phrases(
            book_theme="Test",
            niche="astrology",
            count=30,
            client=client,
        )


def test_malformed_json_raises_runtime_error():
    client = _make_mock_client("this is not JSON {{{")

    with pytest.raises(RuntimeError, match="invalid JSON"):
        generate_phrases(
            book_theme="Test",
            niche="astrology",
            count=30,
            client=client,
        )


def test_phrases_field_not_a_list_raises():
    client = _make_mock_client(json.dumps({"phrases": "not a list"}))

    with pytest.raises(RuntimeError, match="not a list"):
        generate_phrases(
            book_theme="Test",
            niche="astrology",
            count=30,
            client=client,
        )


def test_astrology_invalid_signs_fallback_to_auto_cycle():
    """When LLM returns unknown sign keys, astrology niche fills via SIGN_ORDER cycle."""
    items = [
        {"sign": "not_a_real_sign", "text": f"FRASE {i}."} for i in range(30)
    ]
    client = _make_mock_client(json.dumps({"phrases": items}))

    phrases = generate_phrases(
        book_theme="Test",
        niche="astrology",
        count=30,
        client=client,
    )

    assert len(phrases) == 30
    sign_set = set(SIGN_ORDER)
    for i, item in enumerate(phrases):
        # Each should have been filled via the cycle: SIGN_ORDER[i % 12]
        assert item["subject_key"] in sign_set
        assert item["subject_key"] == SIGN_ORDER[i % len(SIGN_ORDER)]


def test_phrases_as_plain_strings_still_parsed_for_astrology():
    """LLM might respond with strings instead of dicts; still parsed correctly."""
    raw = json.dumps({"phrases": [f"FRASE {i}." for i in range(30)]})
    client = _make_mock_client(raw)

    phrases = generate_phrases(
        book_theme="Test",
        niche="astrology",
        count=30,
        client=client,
    )

    assert len(phrases) == 30
    sign_set = set(SIGN_ORDER)
    for i, item in enumerate(phrases):
        assert item["text"] == f"FRASE {i}."
        # astrology fallback fills subject_key via cycle
        assert item["subject_key"] in sign_set


def test_phrases_as_dict_with_alternate_keys_phrase_and_subject_key():
    """Schema variation: items with 'phrase'/'subject_key' keys instead of 'text'/'sign'."""
    items = [
        {"phrase": f"FRASE {i}.", "subject_key": SIGN_ORDER[i % 12]}
        for i in range(30)
    ]
    client = _make_mock_client(json.dumps({"phrases": items}))

    phrases = generate_phrases(
        book_theme="Test",
        niche="astrology",
        count=30,
        client=client,
    )

    assert len(phrases) == 30
    for i, item in enumerate(phrases):
        assert item["text"] == f"FRASE {i}."
        assert item["subject_key"] == SIGN_ORDER[i % 12]


# ──────────────────────────── prompt construction ──────────────────────────


def test_brief_included_in_user_prompt():
    client = _make_mock_client(_zodiac_response(30))
    brief_text = "MARKER_BRIEF_FOR_TEST_123: tono Mafalda"

    generate_phrases(
        book_theme="Test",
        niche="astrology",
        count=30,
        brief=brief_text,
        client=client,
    )

    args, kwargs = client.chat.completions.create.call_args
    user_msg = kwargs["messages"][1]["content"]
    assert brief_text in user_msg
    assert "Contesto aggiuntivo" in user_msg


def test_empty_brief_not_included_in_user_prompt():
    client = _make_mock_client(_zodiac_response(30))

    generate_phrases(
        book_theme="Test",
        niche="astrology",
        count=30,
        brief="   ",  # whitespace only
        client=client,
    )

    args, kwargs = client.chat.completions.create.call_args
    user_msg = kwargs["messages"][1]["content"]
    assert "Contesto aggiuntivo" not in user_msg


def test_model_param_is_passed_to_api():
    client = _make_mock_client(_zodiac_response(30))

    generate_phrases(
        book_theme="Test",
        niche="astrology",
        count=30,
        client=client,
        model="gpt-4o-mini",
    )

    args, kwargs = client.chat.completions.create.call_args
    assert kwargs["model"] == "gpt-4o-mini"


def test_default_model_is_gpt4o():
    client = _make_mock_client(_zodiac_response(30))

    generate_phrases(book_theme="Test", niche="astrology", count=30, client=client)

    args, kwargs = client.chat.completions.create.call_args
    assert kwargs["model"] == "gpt-4o"


def test_temperature_and_max_tokens_are_reasonable():
    client = _make_mock_client(_zodiac_response(30))

    generate_phrases(book_theme="Test", niche="astrology", count=30, client=client)

    args, kwargs = client.chat.completions.create.call_args
    # Temperature should be elevated for creative output but capped
    assert 0.5 <= kwargs["temperature"] <= 1.5
    # max_tokens should allow ~30 short phrases (~50 tokens each → ~1500)
    assert 1000 <= kwargs["max_tokens"] <= 4096
    # JSON response format requested
    assert kwargs["response_format"] == {"type": "json_object"}


def test_astrology_niche_prompt_lists_signs():
    client = _make_mock_client(_zodiac_response(30))

    generate_phrases(book_theme="Test", niche="astrology", count=30, client=client)

    args, kwargs = client.chat.completions.create.call_args
    user_msg = kwargs["messages"][1]["content"]
    # All 12 canonical signs must be listed somewhere in the user prompt
    for sign in SIGN_ORDER:
        assert sign in user_msg, f"sign '{sign}' missing from astrology prompt"


def test_generic_niche_prompt_uses_generic_template():
    client = _make_mock_client(_generic_response(30))

    generate_phrases(
        book_theme="Office Burnout",
        niche="office_burnout",
        count=30,
        client=client,
    )

    args, kwargs = client.chat.completions.create.call_args
    user_msg = kwargs["messages"][1]["content"]
    assert "office_burnout" in user_msg
    assert "Office Burnout" in user_msg
    # Generic template shouldn't enumerate the 12 zodiac signs
    listed_signs = sum(1 for s in SIGN_ORDER if s in user_msg.lower())
    assert listed_signs < 6, "generic prompt should not include the zodiac sign list"


def test_count_truncates_extra_phrases():
    """If the LLM over-delivers, output is truncated to the requested count."""
    items = [
        {"sign": SIGN_ORDER[i % 12], "text": f"FRASE {i}."} for i in range(50)
    ]
    client = _make_mock_client(json.dumps({"phrases": items}))

    phrases = generate_phrases(
        book_theme="Test",
        niche="astrology",
        count=30,
        client=client,
    )

    assert len(phrases) == 30
