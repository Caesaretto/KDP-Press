"""Listing optimizer: KDP TOS limits + report generation."""
from __future__ import annotations

from listing_optimizer import (
    LISTING_IT, LISTING_EN, _check, generate_listing_report,
    _MAX_TITLE, _MAX_KEYWORD, _MAX_DESC,
)


def test_titles_within_kdp_200_char_limit():
    assert len(LISTING_IT["title"]) <= _MAX_TITLE
    assert len(LISTING_EN["title"]) <= _MAX_TITLE


def test_descriptions_within_kdp_4000_char_limit():
    assert len(LISTING_IT["description"]) <= _MAX_DESC
    assert len(LISTING_EN["description"]) <= _MAX_DESC


def test_each_keyword_within_50_char_limit():
    for listing, label in [(LISTING_IT, "IT"), (LISTING_EN, "EN")]:
        for kw in listing["keywords"]:
            assert len(kw) <= _MAX_KEYWORD, f"{label}: {kw!r} is {len(kw)} chars"


def test_seven_keyword_slots_per_listing():
    assert len(LISTING_IT["keywords"]) == 7
    assert len(LISTING_EN["keywords"]) == 7


def test_max_two_categories_per_listing():
    assert 1 <= len(LISTING_IT["categories"]) <= 2
    assert 1 <= len(LISTING_EN["categories"]) <= 2


def test__check_flags_overflow():
    warns = _check("title", "x" * (_MAX_TITLE + 5), _MAX_TITLE)
    assert warns and "WARNING" in warns[0]


def test__check_passes_under_limit():
    assert _check("title", "ok", _MAX_TITLE) == []


def test_generate_listing_report_writes_non_empty_file(tmp_path):
    out = tmp_path / "report.txt"
    path = generate_listing_report(str(out))
    assert path == str(out)
    contents = out.read_text(encoding="utf-8")
    assert "LISTING IT" in contents
    assert "LISTING EN" in contents
    assert "BACKEND KEYWORDS" in contents
