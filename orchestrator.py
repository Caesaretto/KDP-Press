"""
Book Orchestrator — end-to-end factory pipeline.

Coordinates:
  1. Phrase Agent (LLM) → list of N phrases tagged with subject keys
  2. Loop: for each phrase, generate the illustration via gpt-image-1 + the
     v3 post-processing pipeline (binarize, outline-text framed label)
  3. PDF assembly into a single download-ready book PDF
  4. Metadata + thumbnail persistence to /data/output/books/{ts}_{slug}/

Public API:
    generate_book(title, niche, tone, count, lang, brief, progress, client)
        → Path to the book directory

    list_books() → list[dict] of metadata for the Library UI
"""
from __future__ import annotations

import json
import os
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, TypeVar

from PIL import Image
from openai import OpenAI

import quota
from agents.phrase_agent import generate_phrases
from generate_page import (
    BINARIZE_THR,
    KDP_H,
    KDP_W,
    OUTPUT_DPI,
    binarize,
    build_prompt,
    generate_image,
    outline_text,
    upscale_to_kdp,
)
from zodiac_config import SIGN_ORDER

_T = TypeVar("_T")

# Exceptions worth retrying (transient) vs. terminal (auth/policy)
_RETRYABLE_PATTERNS = (
    "rate limit", "rate_limit", "429",
    "timeout", "timed out", "connection", "temporarily",
    "internal server", "500", "502", "503", "504",
)


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(p in msg for p in _RETRYABLE_PATTERNS)


def _with_retry(fn: Callable[[], _T], max_attempts: int = 4,
                base_delay: float = 2.0) -> _T:
    """Exponential-backoff retry for transient OpenAI errors."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt == max_attempts or not _is_retryable(e):
                raise
            time.sleep(base_delay * (2 ** (attempt - 1)))
    raise last_exc  # type: ignore[misc]


_OUTPUT_BASE = Path(os.environ.get("OUTPUT_BASE", "output"))
BOOKS_DIR    = _OUTPUT_BASE / "books"


def _slugify(text: str, maxlen: int = 50) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:maxlen] or "book"


ProgressFn = Callable[[str, float], None]


def generate_book(
    title: str,
    niche: str = "astrology",
    tone: str = "ironico e sarcastico",
    count: int = 30,
    lang: str = "it",
    brief: str | None = None,
    progress: ProgressFn | None = None,
    client: OpenAI | None = None,
    threshold: int = BINARIZE_THR,
) -> Path:
    """Generate a complete coloring book end-to-end.

    Returns the Path to the book directory containing:
        - book.json (metadata)
        - phrases.json (generated phrases)
        - pages/01_raw.png, 01_final.png, ... (per-page assets)
        - final/{slug}.pdf (assembled book PDF)
        - thumbnail.png (preview for the Library UI)
    """
    if client is None:
        # 120s timeout per call (gpt-image-1 high può prendere 30-60s);
        # max_retries gestito dal nostro _with_retry per consistenza.
        client = OpenAI(timeout=120.0, max_retries=0)

    def emit(msg: str, pct: float) -> None:
        pct = max(0.0, min(1.0, pct))
        if progress:
            progress(msg, pct)

    slug = _slugify(title)
    # Microsecondi → no collisione su double-submit nello stesso secondo.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    book_dir = BOOKS_DIR / f"{ts}_{slug}"
    pages_dir = book_dir / "pages"
    final_dir = book_dir / "final"
    book_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    errors: list[dict] = []

    # ── Step 1: phrases ───────────────────────────────────────────────────────
    emit(f"Generando {count} frasi…", 0.02)
    try:
        phrases = generate_phrases(
            book_theme=title,
            niche=niche,
            tone=tone,
            count=count,
            lang=lang,
            brief=brief,
            client=client,
        )
    except Exception as e:
        emit(f"❌ Phrase agent fallito: {e}", 0.05)
        raise

    (book_dir / "phrases.json").write_text(
        json.dumps(phrases, ensure_ascii=False, indent=2)
    )
    emit(f"✓ Frasi generate: {len(phrases)}", 0.08)

    # ── Step 2: illustrations loop ────────────────────────────────────────────
    final_paths: list[Path] = []
    api_calls_made = 0  # tracks paid attempts (success + retries + final failures)
    for i, item in enumerate(phrases):
        phrase = item["text"]
        subject_key = item.get("subject_key")

        # For astrology niche, use the assigned sign; otherwise cycle SIGN_ORDER
        if niche == "astrology" and subject_key in SIGN_ORDER:
            sign = subject_key
        elif niche == "astrology":
            sign = SIGN_ORDER[i % len(SIGN_ORDER)]
        else:
            # Non-astrology niches not fully supported yet (Phase 2)
            sign = SIGN_ORDER[i % len(SIGN_ORDER)]

        pct = 0.08 + 0.85 * ((i + 0.5) / count)

        # Quota check BEFORE the API call — abort gracefully if cap reached.
        if not quota.consume_one():
            emit(f"⚠️ Quota giornaliera esaurita a pagina {i + 1}/{count}", pct)
            errors.append({
                "page": i + 1, "sign": sign, "phrase": phrase,
                "error": "Quota giornaliera AI esaurita",
                "trace": "",
            })
            break

        emit(f"Illustrazione {i + 1}/{count} ({sign}): {phrase[:48]}…", pct)

        try:
            prompt = build_prompt(sign)
            api_calls_made += 1
            raw = _with_retry(lambda p=prompt: generate_image(p, client))

            raw_path = pages_dir / f"{i + 1:02d}_raw.png"
            raw.save(raw_path)

            kdp = upscale_to_kdp(raw)
            proc = binarize(kdp, threshold)
            final_img = outline_text(proc, phrase)
            final_path = pages_dir / f"{i + 1:02d}_final.png"
            final_img.save(final_path, dpi=(OUTPUT_DPI, OUTPUT_DPI))
            final_paths.append(final_path)
        except Exception as e:
            # Refund quota only for terminal failures we didn't bill — but
            # OpenAI bills failed attempts too in many cases, so refund
            # conservatively only for client-side errors (PIL save, disk).
            errors.append({
                "page": i + 1,
                "sign": sign,
                "phrase": phrase,
                "error": str(e),
                "trace": traceback.format_exc(limit=3),
            })
            emit(f"⚠️ Errore pagina {i + 1}: {str(e)[:80]}", pct)
            continue

    if not final_paths:
        emit("❌ Nessuna illustrazione generata", 1.0)
        raise RuntimeError("Tutte le illustrazioni sono fallite. Verifica API key e quota.")

    # ── Step 3: thumbnail for library ─────────────────────────────────────────
    try:
        thumb = Image.open(final_paths[0]).convert("RGB")
        thumb.thumbnail((400, 600), Image.LANCZOS)
        thumb.save(book_dir / "thumbnail.png")
    except Exception:
        pass  # Thumbnail is cosmetic, never block on it

    # ── Step 4: PDF assembly (memory-safe via img2pdf) ────────────────────────
    # img2pdf streams PNG bytes direttamente nel PDF senza decodare in RAM.
    # Memoria: O(1) per pagina vs O(N) del save_all PIL → no OOM su Railway.
    # Forziamo pagesize a 8.5×11" (KDP letter) per essere indipendenti dal
    # DPI metadata dei PNG (così funziona anche con test images piccole).
    emit("Assemblando PDF…", 0.96)
    pdf_path: Path | None = final_dir / f"{slug}.pdf"
    try:
        import img2pdf
        layout = img2pdf.get_layout_fun(
            pagesize=(img2pdf.in_to_pt(8.5), img2pdf.in_to_pt(11))
        )
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(
                [str(p) for p in final_paths],
                layout_fun=layout,
            ))
    except Exception as e:
        emit(f"⚠️ PDF assembly fallita: {e}", 0.97)
        pdf_path = None

    # ── Step 5: metadata ──────────────────────────────────────────────────────
    # Cost basato su api_calls_made (pagine effettivamente chiamate) NON su
    # final_paths (success) — OpenAI bill anche i fail. Sotto-stima ridotta.
    metadata = {
        "title": title,
        "slug": slug,
        "niche": niche,
        "tone": tone,
        "count_requested": count,
        "count_generated": len(final_paths),
        "lang": lang,
        "brief": brief,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "pdf_path": str(pdf_path.relative_to(book_dir)) if pdf_path else None,
        "thumbnail_path": "thumbnail.png",
        "errors": errors,
        "api_calls_image": api_calls_made,
        "estimated_cost_usd": round(0.01 + 0.20 * api_calls_made, 2),
        "model_phrases": "gpt-4o",
        "model_images": "gpt-image-1",
    }
    (book_dir / "book.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2)
    )

    emit(f"✓ Libro completato: {len(final_paths)}/{count} pagine", 1.0)
    return book_dir


def list_books() -> list[dict]:
    """Return metadata for all generated books, newest first.

    Each entry includes RESOLVED absolute paths for thumbnail, pdf, and book
    dir — server-injected, never trusting strings from book.json itself
    (defense in depth against future code that might persist `_book_dir`).
    Books with missing/corrupt book.json are skipped silently.
    """
    if not BOOKS_DIR.exists():
        return []

    books_root = BOOKS_DIR.resolve()
    books: list[dict] = []
    for book_dir in sorted(BOOKS_DIR.iterdir(), reverse=True):
        if not book_dir.is_dir():
            continue
        # Ensure each book_dir is genuinely under BOOKS_DIR (symlink hardening)
        try:
            resolved = book_dir.resolve()
            resolved.relative_to(books_root)
        except ValueError:
            continue
        meta_path = resolved / "book.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            continue
        meta["_book_dir"] = str(resolved)
        thumb = resolved / "thumbnail.png"
        meta["_thumbnail"] = str(thumb) if thumb.is_file() else None
        if meta.get("pdf_path"):
            pdf = resolved / meta["pdf_path"]
            # Validate the PDF stays within book_dir (defense vs malicious json)
            try:
                pdf.resolve().relative_to(resolved)
                meta["_pdf_path"] = str(pdf) if pdf.is_file() else None
            except ValueError:
                meta["_pdf_path"] = None
        else:
            meta["_pdf_path"] = None
        books.append(meta)
    return books


def get_book_pages(book_dir: Path) -> list[Path]:
    """Return all `_final.png` page paths for a book, in order."""
    pages_dir = book_dir / "pages"
    if not pages_dir.exists():
        return []
    return sorted(pages_dir.glob("*_final.png"))
