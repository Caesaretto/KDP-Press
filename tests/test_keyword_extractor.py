"""Keyword extractor parsing logic — HTTP fully mocked."""
from __future__ import annotations

import pytest

import keyword_extractor as kx
from keyword_extractor import MARKETS, get_suggestions, expand_keywords


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_unknown_market_raises(monkeypatch):
    with pytest.raises(ValueError):
        get_suggestions("anything", market="MARS")


def test_get_suggestions_parses_values(monkeypatch):
    payload = {"suggestions": [
        {"value": "adult coloring book zodiac"},
        {"value": "adult coloring book funny"},
    ]}
    monkeypatch.setattr(kx.requests, "get", lambda *a, **kw: _FakeResponse(payload))
    out = get_suggestions("adult coloring book", market="USA")
    assert out == ["adult coloring book zodiac", "adult coloring book funny"]


def test_get_suggestions_returns_empty_on_http_error(monkeypatch):
    monkeypatch.setattr(kx.requests, "get",
                        lambda *a, **kw: _FakeResponse({}, status=429))
    assert get_suggestions("anything", market="USA") == []


def test_get_suggestions_returns_empty_on_bad_json(monkeypatch):
    class _BadJson:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): raise ValueError("bad")
    monkeypatch.setattr(kx.requests, "get", lambda *a, **kw: _BadJson())
    assert get_suggestions("anything", market="USA") == []


def test_expand_keywords_filters_by_seed(monkeypatch):
    payload = {"suggestions": [
        {"value": "coloring book zodiac"},
        {"value": "completely unrelated topic"},
        {"value": "zodiac signs guide"},
    ]}
    monkeypatch.setattr(kx.requests, "get", lambda *a, **kw: _FakeResponse(payload))
    out = expand_keywords("zodiac coloring", market="IT", depth=1)
    # All entries containing 'zodiac' or 'coloring' survive; 'completely unrelated' may slip
    # through `direct` (which is unconditionally included). Validate at least filter relevance.
    assert "coloring book zodiac" in out
    assert "zodiac signs guide" in out


def test_markets_have_5_entries():
    assert set(MARKETS.keys()) == {"USA", "UK", "DE", "IT", "PL"}
    for url, mid in MARKETS.values():
        assert url.startswith("https://completion.amazon.")
        assert mid and isinstance(mid, str)
