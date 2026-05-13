"""Lightweight integration tests for app.py — Streamlit pages.

We don't run Streamlit's server; we only verify:
  - the new page functions import cleanly,
  - the navigation radio includes the two new entries in the correct order,
  - _init_session() seeds nav_page with "✨ Nuovo Libro" by default.
"""
from __future__ import annotations

import inspect

import pytest


# ─────────────────── module import & symbols ──────────────────────────────


def test_app_imports_without_error():
    """Importing app.py must not raise (Streamlit warnings are tolerated)."""
    import app  # noqa: F401


def test_page_new_book_is_importable_callable():
    import app
    assert hasattr(app, "page_new_book")
    assert callable(app.page_new_book)


def test_page_library_is_importable_callable():
    import app
    assert hasattr(app, "page_library")
    assert callable(app.page_library)


def test_init_session_is_importable_callable():
    import app
    assert hasattr(app, "_init_session")
    assert callable(app._init_session)


# ─────────────────── navigation contains the new pages ────────────────────


def test_nav_radio_includes_new_book_and_library_in_order():
    """The sidebar nav_options list must list ✨ Nuovo Libro first, then 📚 Libreria."""
    import app
    src = inspect.getsource(app.main)
    assert "✨ Nuovo Libro" in src, "Nuovo Libro missing from main() nav"
    assert "📚 Libreria" in src, "Libreria missing from main() nav"
    # Order: Nuovo Libro before Libreria, Libreria before Dashboard
    assert src.index("✨ Nuovo Libro") < src.index("📚 Libreria")
    assert src.index("📚 Libreria") < src.index("🏠 Dashboard")


def test_main_routes_to_page_new_book_and_page_library():
    """main() must call both new page functions."""
    import app
    src = inspect.getsource(app.main)
    assert "page_new_book()" in src
    assert "page_library()" in src


# ─────────────────── _init_session default value ──────────────────────────


def test_init_session_default_nav_page_in_source():
    """The default nav_page string is "✨ Nuovo Libro"."""
    import app
    src = inspect.getsource(app._init_session)
    assert '"nav_page"' in src
    assert "✨ Nuovo Libro" in src


def test_init_session_sets_nav_page_default(monkeypatch, tmp_path):
    """Functional check: calling _init_session() seeds nav_page correctly.

    We swap st.session_state with a plain dict-attr stand-in and PROJECT_FILE
    with a non-existent path so the function takes the default branch.
    """
    import app

    class FakeSessionState(dict):
        """Mimics streamlit.session_state: dict + attribute access."""
        def __getattr__(self, k):
            try:
                return self[k]
            except KeyError as e:
                raise AttributeError(k) from e

        def __setattr__(self, k, v):
            self[k] = v

    fake = FakeSessionState()
    monkeypatch.setattr(app.st, "session_state", fake)
    monkeypatch.setattr(app, "PROJECT_FILE", tmp_path / "no_such_file.json")

    app._init_session()

    assert fake["nav_page"] == "✨ Nuovo Libro"
    # The other defaults should also be seeded
    assert "qr_url" in fake
    assert "gen_log" in fake
    assert "project" in fake
    assert fake["project"] == {"niche": None, "pages": []}


def test_init_session_preserves_existing_nav_page(monkeypatch, tmp_path):
    """If nav_page is already set, _init_session() must not overwrite it."""
    import app

    class FakeSessionState(dict):
        def __getattr__(self, k):
            try:
                return self[k]
            except KeyError as e:
                raise AttributeError(k) from e

        def __setattr__(self, k, v):
            self[k] = v

    fake = FakeSessionState()
    fake["nav_page"] = "🎨 Studio Mode"
    monkeypatch.setattr(app.st, "session_state", fake)
    monkeypatch.setattr(app, "PROJECT_FILE", tmp_path / "no_such_file.json")

    app._init_session()
    assert fake["nav_page"] == "🎨 Studio Mode"


# ─────────────────── page functions reference orchestrator ────────────────


def test_page_new_book_uses_orchestrator():
    import app
    src = inspect.getsource(app.page_new_book)
    assert "orchestrator" in src
    assert "generate_book" in src


def test_page_library_uses_orchestrator():
    import app
    src = inspect.getsource(app.page_library)
    assert "orchestrator" in src
    assert "list_books" in src
