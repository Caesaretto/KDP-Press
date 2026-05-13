"""Tests for orchestrator.py — generate_book(), list_books(), _slugify().

All OpenAI calls and image-generation calls are mocked. Filesystem operations
are redirected to pytest's tmp_path via the OUTPUT_BASE env var.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image


# ─────────────────────────── fixtures ─────────────────────────────────────


@pytest.fixture
def orch(tmp_path, monkeypatch):
    """Reload the orchestrator module so OUTPUT_BASE picks up tmp_path."""
    monkeypatch.setenv("OUTPUT_BASE", str(tmp_path))
    import orchestrator as _orch
    importlib.reload(_orch)
    return _orch


@pytest.fixture
def fake_phrases():
    """30 astrology phrases as the phrase agent would return them."""
    from zodiac_config import SIGN_ORDER
    return [
        {"text": f"FRASE {i + 1}.", "subject_key": SIGN_ORDER[i % 12]}
        for i in range(30)
    ]


def _tiny_image() -> Image.Image:
    """Small in-memory white PIL image for fast tests."""
    return Image.new("RGB", (10, 10), "white")


def _patch_pipeline(monkeypatch, orch, phrases, image_factory=None,
                    fail_indices: set[int] | None = None):
    """Patch phrase agent + image-pipeline functions on the orchestrator module.

    image_factory: callable() -> PIL.Image. Defaults to a tiny white 10x10.
    fail_indices: set of 0-based page indices where generate_image should raise.
    """
    if image_factory is None:
        image_factory = _tiny_image
    fail_indices = fail_indices or set()

    # Mock phrase generation
    monkeypatch.setattr(orch, "generate_phrases", lambda **kw: phrases)

    # Track calls to generate_image so we can fail selectively
    call_counter = {"n": 0}

    def fake_generate_image(prompt, client):
        i = call_counter["n"]
        call_counter["n"] += 1
        if i in fail_indices:
            raise RuntimeError(f"injected image failure at call {i}")
        return image_factory()

    monkeypatch.setattr(orch, "generate_image", fake_generate_image)

    # Pipeline functions: keep them lightweight, no real heavy processing
    monkeypatch.setattr(orch, "build_prompt", lambda sign: f"prompt-for-{sign}")
    monkeypatch.setattr(orch, "upscale_to_kdp", lambda img: img)
    monkeypatch.setattr(orch, "binarize", lambda img, threshold=160: img)
    monkeypatch.setattr(orch, "outline_text", lambda img, phrase: img)
    return call_counter


# ─────────────────────────── _slugify ─────────────────────────────────────


def test_slugify_spaces_and_case(orch):
    assert orch._slugify("Zodiacale Esaurito") == "zodiacale_esaurito"


def test_slugify_special_chars(orch):
    assert orch._slugify("Hello, World!") == "hello_world"
    # Slashes, colons, etc. collapse to single underscores
    assert orch._slugify("a/b:c|d") == "a_b_c_d"


def test_slugify_accents_dropped(orch):
    """Accented characters fall outside [a-z0-9] and collapse to underscores."""
    out = orch._slugify("Caffé Brûlé")
    # The exact representation depends on regex; verify it's a valid slug
    assert out
    assert all(c.isalnum() or c == "_" for c in out)
    assert not out.startswith("_") and not out.endswith("_")


def test_slugify_empty_string_returns_default(orch):
    assert orch._slugify("") == "book"


def test_slugify_only_special_chars_returns_default(orch):
    assert orch._slugify("!!!@@@###") == "book"


def test_slugify_truncates_to_maxlen(orch):
    long = "a" * 200
    out = orch._slugify(long, maxlen=50)
    assert len(out) == 50


def test_slugify_default_maxlen_50(orch):
    long = "a" * 200
    assert len(orch._slugify(long)) == 50


# ─────────────────────────── generate_book happy path ─────────────────────


def test_generate_book_happy_path_creates_all_artefacts(
    orch, tmp_path, monkeypatch, fake_phrases
):
    _patch_pipeline(monkeypatch, orch, fake_phrases)
    client = MagicMock()

    book_dir = orch.generate_book(
        title="Zodiacale Esaurito",
        niche="astrology",
        count=30,
        client=client,
    )

    assert isinstance(book_dir, Path)
    assert book_dir.exists() and book_dir.is_dir()
    # Book directory under tmp_path/books/
    assert book_dir.parent == tmp_path / "books"
    # Slug present in directory name
    assert "zodiacale_esaurito" in book_dir.name

    # phrases.json
    phrases_path = book_dir / "phrases.json"
    assert phrases_path.exists()
    saved = json.loads(phrases_path.read_text())
    assert len(saved) == 30

    # book.json
    meta_path = book_dir / "book.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta["title"] == "Zodiacale Esaurito"
    assert meta["slug"] == "zodiacale_esaurito"
    assert meta["niche"] == "astrology"
    assert meta["count_requested"] == 30
    assert meta["count_generated"] == 30
    assert meta["errors"] == []
    assert meta["estimated_cost_usd"] > 0
    assert meta["model_phrases"] == "gpt-4o"
    assert meta["model_images"] == "gpt-image-1"

    # 30 pages: raw + final each
    pages_dir = book_dir / "pages"
    raws = sorted(pages_dir.glob("*_raw.png"))
    finals = sorted(pages_dir.glob("*_final.png"))
    assert len(raws) == 30
    assert len(finals) == 30

    # final PDF
    pdf_rel = meta["pdf_path"]
    assert pdf_rel and (book_dir / pdf_rel).exists()
    assert (book_dir / pdf_rel).stat().st_size > 0

    # thumbnail
    assert (book_dir / "thumbnail.png").exists()


def test_generate_book_writes_correct_phrases(
    orch, monkeypatch, fake_phrases
):
    _patch_pipeline(monkeypatch, orch, fake_phrases)
    book_dir = orch.generate_book(
        title="Test Book", niche="astrology", count=30, client=MagicMock()
    )
    saved = json.loads((book_dir / "phrases.json").read_text())
    assert saved == fake_phrases


# ─────────────────────────── partial failures ─────────────────────────────


def test_generate_book_continues_on_some_image_failures(
    orch, monkeypatch, fake_phrases
):
    # Fail pages 5, 12, 20 (0-based)
    fail = {5, 12, 20}
    _patch_pipeline(monkeypatch, orch, fake_phrases, fail_indices=fail)

    book_dir = orch.generate_book(
        title="Resilient", niche="astrology", count=30, client=MagicMock()
    )
    meta = json.loads((book_dir / "book.json").read_text())

    assert meta["count_generated"] == 30 - len(fail) == 27
    assert len(meta["errors"]) == len(fail)
    # Each error entry must include diagnostic fields
    for err in meta["errors"]:
        assert "page" in err and "sign" in err and "phrase" in err
        assert "error" in err and "trace" in err
        assert "injected image failure" in err["error"]


def test_generate_book_all_image_failures_raises(
    orch, monkeypatch, fake_phrases
):
    _patch_pipeline(
        monkeypatch, orch, fake_phrases, fail_indices=set(range(30))
    )

    with pytest.raises(RuntimeError, match="illustrazioni"):
        orch.generate_book(
            title="Doomed", niche="astrology", count=30, client=MagicMock()
        )


def test_generate_book_phrase_agent_failure_propagates(orch, monkeypatch):
    def boom(**kw):
        raise RuntimeError("simulated phrase-agent crash")
    monkeypatch.setattr(orch, "generate_phrases", boom)
    # Image-pipeline patches not strictly needed; we should crash before them
    monkeypatch.setattr(orch, "generate_image", lambda *a, **k: _tiny_image())
    monkeypatch.setattr(orch, "build_prompt", lambda s: "p")
    monkeypatch.setattr(orch, "upscale_to_kdp", lambda i: i)
    monkeypatch.setattr(orch, "binarize", lambda i, threshold=160: i)
    monkeypatch.setattr(orch, "outline_text", lambda i, p: i)

    with pytest.raises(RuntimeError, match="simulated phrase-agent crash"):
        orch.generate_book(
            title="x", niche="astrology", count=30, client=MagicMock()
        )


# ─────────────────────────── progress callback ────────────────────────────


def test_generate_book_progress_callback_is_monotonic_and_bounded(
    orch, monkeypatch, fake_phrases
):
    _patch_pipeline(monkeypatch, orch, fake_phrases)
    events: list[tuple[str, float]] = []

    def progress(msg: str, pct: float) -> None:
        events.append((msg, pct))

    orch.generate_book(
        title="Track",
        niche="astrology",
        count=30,
        client=MagicMock(),
        progress=progress,
    )

    assert len(events) > 5, "progress callback should fire repeatedly"
    pcts = [p for _, p in events]
    assert all(0.0 <= p <= 1.0 for p in pcts), f"out-of-range pct: {pcts}"
    # Monotonic non-decreasing
    for prev, curr in zip(pcts, pcts[1:]):
        assert curr >= prev, f"progress went backwards: {prev} -> {curr}"
    # Reaches 1.0 by the end
    assert pcts[-1] == pytest.approx(1.0)
    # Starts close to 0
    assert pcts[0] <= 0.1


def test_generate_book_works_without_progress_callback(
    orch, monkeypatch, fake_phrases
):
    _patch_pipeline(monkeypatch, orch, fake_phrases)
    # progress=None must not raise
    book_dir = orch.generate_book(
        title="No-Progress", niche="astrology", count=30, client=MagicMock()
    )
    assert (book_dir / "book.json").exists()


# ─────────────────────────── OUTPUT_BASE env ──────────────────────────────


def test_output_base_env_var_is_respected(tmp_path, monkeypatch, fake_phrases):
    custom = tmp_path / "custom_root"
    monkeypatch.setenv("OUTPUT_BASE", str(custom))

    import orchestrator as _orch
    importlib.reload(_orch)

    _patch_pipeline(monkeypatch, _orch, fake_phrases)
    book_dir = _orch.generate_book(
        title="Custom Root", niche="astrology", count=30, client=MagicMock()
    )
    assert str(book_dir).startswith(str(custom / "books"))


# ─────────────────────────── list_books ───────────────────────────────────


def test_list_books_empty_dir_returns_empty_list(orch):
    # BOOKS_DIR doesn't exist yet → must return [] without crashing
    assert orch.list_books() == []


def test_list_books_populated_dir(orch, monkeypatch, fake_phrases):
    _patch_pipeline(monkeypatch, orch, fake_phrases)
    # Generate two books
    b1 = orch.generate_book(
        title="First", niche="astrology", count=6, client=MagicMock()
    )
    # The pipeline expects count phrases; rebuild fake_phrases at correct size
    monkeypatch.setattr(
        orch, "generate_phrases",
        lambda **kw: fake_phrases[:kw.get("count", 30)]
    )
    b2 = orch.generate_book(
        title="Second", niche="astrology", count=6, client=MagicMock()
    )

    books = orch.list_books()
    assert len(books) == 2
    titles = {b["title"] for b in books}
    assert titles == {"First", "Second"}

    # Each entry has the augmented helper paths
    for b in books:
        assert "_book_dir" in b
        assert "_thumbnail" in b
        assert "_pdf_path" in b
        # _pdf_path resolved absolute and existing
        if b["_pdf_path"]:
            assert Path(b["_pdf_path"]).exists()


def test_list_books_skips_malformed_book_json(orch):
    # Pre-create a book dir with broken book.json — no patching needed
    bad = orch.BOOKS_DIR / "20990101_120000_broken"
    bad.mkdir(parents=True, exist_ok=True)
    (bad / "book.json").write_text("{not valid json")

    # Should not raise and should silently skip
    result = orch.list_books()
    assert result == []


def test_list_books_skips_dir_without_book_json(orch):
    empty = orch.BOOKS_DIR / "20990101_120000_empty"
    empty.mkdir(parents=True, exist_ok=True)
    # No book.json at all → silently skipped
    assert orch.list_books() == []
