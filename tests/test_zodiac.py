"""Zodiac config + phrases invariants."""
from __future__ import annotations

from frasi_zodiacali import FRASI
from zodiac_config import SIGN_ORDER, ZODIAC_CONFIG


def test_sign_order_has_12_unique_signs():
    assert len(SIGN_ORDER) == 12
    assert len(set(SIGN_ORDER)) == 12


def test_zodiac_config_covers_all_signs():
    assert set(ZODIAC_CONFIG.keys()) >= set(SIGN_ORDER)


def test_frasi_has_all_12_signs_in_both_languages():
    assert set(FRASI.keys()) == set(SIGN_ORDER)
    for sign, langs in FRASI.items():
        assert "it" in langs and "en" in langs, f"{sign} missing a language"


def test_frasi_total_count_is_30_per_language():
    """30 illustrations target = 30 phrases (12 signs × 2 + 6 signs × 1 extra)."""
    for lang in ("it", "en"):
        total = sum(len(FRASI[sign][lang]) for sign in SIGN_ORDER)
        assert total == 30, f"{lang}: expected 30, got {total}"


def test_each_phrase_within_word_limits():
    for sign, langs in FRASI.items():
        for lang, phrases in langs.items():
            for phrase in phrases:
                assert phrase.strip() == phrase, f"{sign}/{lang}: leading/trailing whitespace"
                words = phrase.split()
                assert 1 <= len(words) <= 12, (
                    f"{sign}/{lang}: '{phrase}' has {len(words)} words (expected 1-12)"
                )


def test_no_duplicate_phrases_within_a_sign():
    for sign, langs in FRASI.items():
        for lang, phrases in langs.items():
            assert len(phrases) == len(set(phrases)), f"{sign}/{lang}: duplicate phrases"


def test_phrase_counts_match_languages_per_sign():
    """it and en lists should have the same length for each sign."""
    for sign, langs in FRASI.items():
        assert len(langs["it"]) == len(langs["en"]), (
            f"{sign}: it={len(langs['it'])}, en={len(langs['en'])} mismatch"
        )
