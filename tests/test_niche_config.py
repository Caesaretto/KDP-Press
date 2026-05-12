"""Niche dict structure invariants — catches drift when adding new niches."""
from __future__ import annotations

import pytest

from niche_config import NICHES


REQUIRED_NICHE_KEYS = {"name", "emoji", "description", "subjects"}
REQUIRED_SUBJECT_KEYS = {"key", "label", "simbolo_angolo", "simbolo_lato", "soggetto_kawaii"}


def test_niches_dict_is_non_empty():
    assert isinstance(NICHES, dict)
    assert len(NICHES) >= 10, f"expected at least 10 niches, got {len(NICHES)}"


@pytest.mark.parametrize("niche_key", list(NICHES.keys()))
def test_niche_has_required_top_level_keys(niche_key):
    niche = NICHES[niche_key]
    missing = REQUIRED_NICHE_KEYS - set(niche.keys())
    assert not missing, f"{niche_key}: missing keys {missing}"
    for k in ("name", "emoji", "description"):
        assert isinstance(niche[k], str) and niche[k].strip(), f"{niche_key}: empty {k}"


@pytest.mark.parametrize("niche_key", list(NICHES.keys()))
def test_niche_subjects_well_formed(niche_key):
    """`subjects` is either the literal string 'zodiac' or a list of subject dicts."""
    subjects = NICHES[niche_key]["subjects"]
    if subjects == "zodiac":
        return  # astrology niche delegates to zodiac_config
    assert isinstance(subjects, list) and subjects, f"{niche_key}: empty subjects list"
    seen_keys = set()
    for s in subjects:
        assert isinstance(s, dict)
        missing = REQUIRED_SUBJECT_KEYS - set(s.keys())
        assert not missing, f"{niche_key}/{s.get('key', '?')}: missing {missing}"
        for k in REQUIRED_SUBJECT_KEYS:
            assert isinstance(s[k], str) and s[k].strip(), f"{niche_key}/{s.get('key')}: empty {k}"
        assert s["key"] not in seen_keys, f"{niche_key}: duplicate subject key {s['key']}"
        seen_keys.add(s["key"])


def test_master_prompt_renders_for_each_subject():
    """Every subject must populate the prompt template fields without KeyError."""
    template = "corner: {simbolo_angolo} | side: {simbolo_lato} | subject: {soggetto_kawaii}"
    for niche_key, niche in NICHES.items():
        subjects = niche["subjects"]
        if subjects == "zodiac":
            continue
        for s in subjects:
            rendered = template.format(**s)
            assert rendered.strip(), f"{niche_key}/{s['key']}: empty render"
