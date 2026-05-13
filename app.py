#!/usr/bin/env python3
"""
KDP Publishing House — Streamlit Web App
Run: streamlit run app.py
"""

import io
import json
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image, ImageDraw

# ── Internal imports ──────────────────────────────────────────────────────────
from niche_config import NICHES, NICHE_ORDER
from zodiac_config import ZODIAC_CONFIG, SIGN_ORDER
from generate_page import (
    MASTER_PROMPT_TEMPLATE,
    generate_image,
    binarize,
    enforce_white_text_zone,
    upscale_to_kdp,
    inject_text,
    KDP_W, KDP_H, OUTPUT_DPI, BINARIZE_THR,
)
from special_pages import (
    make_qr_page, make_frontespizio, make_test_colors, make_black_page,
    make_review_page, make_collection_page,
)
from frasi_zodiacali import FRASI
from keyword_extractor import expand_keywords, MARKETS
from landing_page_generator import generate_landing_page
import pdf_assembler

# ── Paths ─────────────────────────────────────────────────────────────────────
# OUTPUT_BASE è override-abile via env (Railway monta volume persistente su /data/output).
# Default "output/" per uso locale in sviluppo.
OUTPUT_BASE    = Path(os.environ.get("OUTPUT_BASE", "output"))
OUTPUT_PAGES   = OUTPUT_BASE / "pages"
OUTPUT_SPECIAL = OUTPUT_BASE / "special"
OUTPUT_FINAL   = OUTPUT_BASE / "final"
PROJECT_FILE   = OUTPUT_BASE / "current_project.json"
THUMB_W, THUMB_H = 120, 160

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KDP Publishing House",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

_CSS = """
<style>
[data-testid="stSidebar"] { min-width: 220px; }
.niche-card {
    border: 2px solid #333; border-radius: 12px;
    padding: 1rem; text-align: center; cursor: pointer;
    transition: border-color .2s, background .2s;
    height: 130px; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 4px;
}
.niche-card:hover { border-color: #e94560; background: rgba(233,69,96,.08); }
.niche-selected { border-color: #e94560 !important; background: rgba(233,69,96,.15) !important; }
.page-thumb {
    border: 1px solid #444; border-radius: 6px;
    padding: 4px; text-align: center; background: #111;
}
.stat-box {
    background: #1a1a2e; border-radius: 10px;
    padding: 1.2rem; text-align: center;
}
.stat-box h3 { font-size: 2rem; color: #e94560; margin: 0; }
.stat-box p  { font-size: 0.85rem; opacity: 0.7; margin: 0; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════

def _init_session() -> None:
    if "project" not in st.session_state:
        if PROJECT_FILE.exists():
            try:
                st.session_state.project = json.loads(PROJECT_FILE.read_text())
            except Exception:
                st.session_state.project = {"niche": None, "pages": []}
        else:
            st.session_state.project = {"niche": None, "pages": []}

    defaults = {
        "qr_url":      "https://thedailyburnoutpress.com/bonus",
        "nav_page":    "🏠 Dashboard",
        "gen_log":     "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _save_project() -> None:
    PROJECT_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROJECT_FILE.write_text(json.dumps(st.session_state.project, indent=2))


def _add_page(page_type: str, path: Path, meta: dict | None = None) -> None:
    entry = {"type": page_type, "path": str(path), **(meta or {})}
    st.session_state.project["pages"].append(entry)
    _save_project()


def _count_illustrations() -> int:
    return sum(1 for p in st.session_state.project["pages"] if p["type"] == "illustration")


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _thumb(img_path: str | Path) -> bytes | None:
    try:
        img = Image.open(img_path).convert("RGB")
        img.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def _get_api_key() -> str:
    """API key è server-side only. Non esponibile mai al frontend."""
    return os.environ.get("OPENAI_API_KEY", "").strip()


DAILY_IMAGE_CAP = int(os.environ.get("DAILY_IMAGE_CAP", "50"))
QUOTA_FILE = OUTPUT_BASE / ".quota.json"


def _load_quota() -> dict:
    if not QUOTA_FILE.exists():
        return {}
    try:
        return json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_quota(data: dict) -> None:
    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUOTA_FILE.write_text(json.dumps(data), encoding="utf-8")


def _check_image_quota() -> None:
    """Enforce a daily cap on AI image generations, persisted in output/.quota.json
    so refresh / new tabs can't bypass it. Raises a Streamlit error and halts
    execution when exceeded.
    """
    today = datetime.now().date().isoformat()
    quota = _load_quota()
    count = int(quota.get(today, 0))
    if count >= DAILY_IMAGE_CAP:
        st.error(
            f"Quota giornaliera raggiunta ({DAILY_IMAGE_CAP} immagini). "
            f"Riprova domani o aumenta DAILY_IMAGE_CAP nelle env vars."
        )
        st.stop()
    quota[today] = count + 1
    # Keep only the last 7 days of history
    keys = sorted(quota.keys())
    if len(keys) > 7:
        for k in keys[:-7]:
            quota.pop(k, None)
    _save_quota(quota)
    # Mirror the count in session_state for live UI display
    st.session_state["img_quota_date"] = today
    st.session_state["img_quota_count"] = count + 1


def _generate_illustration(
    soggetto_kawaii: str,
    phrase: str,
    *,
    glyph_unicode: str = "★",
    thematic_prop: str = "a small thematic prop",
    scatter_elements: str = "small 5-pointed stars, tiny hearts, small swirls",
    threshold: int = BINARIZE_THR,
    # Legacy v1 kwargs kept for backward-compat with older callers (ignored by v2 template)
    simbolo_angolo: str | None = None,
    simbolo_lato: str | None = None,
) -> Path:
    from openai import OpenAI

    client = OpenAI(api_key=_get_api_key() or None)
    prompt = MASTER_PROMPT_TEMPLATE.format(
        glyph_unicode=glyph_unicode,
        soggetto_kawaii=soggetto_kawaii,
        thematic_prop=thematic_prop,
        scatter_elements=scatter_elements,
    )
    _check_image_quota()
    raw   = generate_image(prompt, client)
    OUTPUT_PAGES.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Salviamo il raw per debug (cosa l'AI ha effettivamente prodotto)
    raw_path = OUTPUT_PAGES / f"page_{ts}_raw.png"
    raw.save(raw_path)
    kdp   = upscale_to_kdp(raw)
    proc  = binarize(kdp, threshold)
    proc  = enforce_white_text_zone(proc)
    final = inject_text(proc, phrase)
    path = OUTPUT_PAGES / f"page_{ts}_final.png"
    final.save(path, dpi=(OUTPUT_DPI, OUTPUT_DPI))
    return path


def _generate_zodiac_illustration(sign: str, phrase: str, idx: int,
                                  threshold: int = BINARIZE_THR) -> Path:
    """Generate one zodiac illustration and save with a pdf_assembler-compatible
    filename (`{sign}_{ts}_{idx}_final.png` in output/pages/)."""
    from openai import OpenAI
    cfg = ZODIAC_CONFIG[sign]
    prompt = MASTER_PROMPT_TEMPLATE.format(
        glyph_unicode=cfg.get("glyph_unicode", "★"),
        soggetto_kawaii=cfg["soggetto_kawaii"],
        thematic_prop=cfg.get("thematic_prop", "a small thematic prop"),
        scatter_elements=cfg.get(
            "scatter_elements",
            "small 5-pointed stars, tiny hearts, small swirls",
        ),
    )
    _check_image_quota()
    client = OpenAI(api_key=_get_api_key() or None)
    raw   = generate_image(prompt, client)
    kdp   = upscale_to_kdp(raw)
    proc  = binarize(kdp, threshold)
    proc  = enforce_white_text_zone(proc)
    final = inject_text(proc, phrase)
    OUTPUT_PAGES.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_PAGES / f"{sign}_{ts}_{idx:02d}_final.png"
    final.save(path, dpi=(OUTPUT_DPI, OUTPUT_DPI))
    return path


def _build_all_special_pages(qr_url: str | None = None) -> list[Path]:
    """Render the 6 special pages (front + back matter + black separator)."""
    OUTPUT_SPECIAL.mkdir(parents=True, exist_ok=True)
    url = qr_url or st.session_state.get("qr_url", "https://thedailyburnoutpress.com/bonus")
    saved: list[Path] = []
    builders = [
        ("01_qr_code.png",       lambda: make_qr_page(url)),
        ("02_frontespizio.png",  make_frontespizio),
        ("03_test_colors.png",   make_test_colors),
        ("black_separator.png",  make_black_page),
        ("98_review.png",        lambda: make_review_page(url)),
        ("99_collection.png",    make_collection_page),
    ]
    for fname, build in builders:
        img = build()
        out = OUTPUT_SPECIAL / fname
        img.save(out, dpi=(OUTPUT_DPI, OUTPUT_DPI))
        saved.append(out)
    return saved


def _assemble_full_book_pdf(lang: str = "it",
                            output_name: str = "zodiacale_v1.pdf") -> tuple[bytes, dict]:
    """Run pdf_assembler over output/pages + output/special, return (bytes, qc)."""
    pages = pdf_assembler.collect_pages(lang, target_illustrations=pdf_assembler.TARGET_ILLUSTRATIONS)
    qc = pdf_assembler.qc_report(pages, target=pdf_assembler.TARGET_PAGES)
    OUTPUT_FINAL.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_FINAL / Path(output_name).name
    pdf_assembler.assemble_pdf(pages, out_path)
    return out_path.read_bytes(), qc


def _assemble_pdf_bytes() -> bytes:
    pages = st.session_state.project["pages"]
    allowed_roots = [
        OUTPUT_PAGES.resolve(),
        OUTPUT_SPECIAL.resolve(),
        OUTPUT_FINAL.resolve(),
    ]
    images: list[Image.Image] = []
    for p in pages:
        try:
            page_path = Path(p["path"]).resolve()
            if not any(
                str(page_path).startswith(str(root) + os.sep) or page_path == root
                for root in allowed_roots
            ):
                continue
            img = Image.open(page_path).convert("RGB")
            if img.size != (KDP_W, KDP_H):
                img = img.resize((KDP_W, KDP_H), Image.LANCZOS)
            images.append(img)
        except Exception:
            pass
    if not images:
        return b""
    buf = io.BytesIO()
    images[0].save(
        buf, format="PDF", save_all=True,
        append_images=images[1:],
        resolution=OUTPUT_DPI,
    )
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def page_dashboard() -> None:
    st.title("📚 KDP Publishing House")
    st.caption("The Daily Burnout Press — Fabbrica Editoriale Digitale")

    # Stats
    proj      = st.session_state.project
    illus_cnt = _count_illustrations()
    total_pgs = len(proj["pages"])

    c1, c2, c3 = st.columns(3)
    for col, val, label in [
        (c1, len(NICHES), "Nicchie Disponibili"),
        (c2, illus_cnt,   "Illustrazioni nel Progetto"),
        (c3, "100%" if total_pgs > 0 else "—", "KDP Compliance"),
    ]:
        col.markdown(
            f'<div class="stat-box"><h3>{val}</h3><p>{label}</p></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # Current project info
    if proj["niche"]:
        niche = NICHES.get(proj["niche"], {})
        st.success(
            f"**Progetto attivo:** {niche.get('emoji','')} {niche.get('name', proj['niche'])} — "
            f"{illus_cnt}/30 illustrazioni — {total_pgs} pagine totali"
        )

    st.subheader("Seleziona la Nicchia")
    st.caption("Clicca una nicchia per iniziare o continuare un progetto")

    # Niche grid — 5 per row
    niche_keys = NICHE_ORDER
    rows = [niche_keys[i:i+5] for i in range(0, len(niche_keys), 5)]

    for row in rows:
        cols = st.columns(len(row))
        for col, key in zip(cols, row):
            n = NICHES[key]
            is_active = proj["niche"] == key
            with col:
                btn_label = f"{n['emoji']}\n**{n['name']}**"
                if st.button(
                    f"{n['emoji']} {n['name']}",
                    key=f"niche_{key}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                    help=n.get("description", ""),
                ):
                    st.session_state.project["niche"] = key
                    _save_project()
                    st.session_state.nav_page = "📚 Book Builder"
                    st.rerun()

    # Recent projects
    st.divider()
    st.subheader("File Generati di Recente")
    recent = sorted(OUTPUT_PAGES.glob("*_final.png"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
    if recent:
        cols = st.columns(min(len(recent), 5))
        for i, path in enumerate(recent[:5]):
            with cols[i]:
                t = _thumb(path)
                if t:
                    st.image(t, caption=path.name[:20], use_container_width=True)
    else:
        st.info("Nessuna illustrazione generata ancora. Seleziona una nicchia per iniziare.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: BOOK BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def page_book_builder() -> None:
    proj  = st.session_state.project
    niche_key = proj.get("niche")

    st.title("📚 Book Builder")

    if not niche_key:
        st.warning("Prima seleziona una nicchia dalla Dashboard.")
        if st.button("← Vai alla Dashboard"):
            st.session_state.nav_page = "🏠 Dashboard"
            st.rerun()
        return

    niche = NICHES[niche_key]
    illus_cnt = _count_illustrations()

    st.caption(f"{niche['emoji']} {niche['name']} — {illus_cnt}/30 illustrazioni")
    st.progress(min(illus_cnt / 30, 1.0), text=f"{illus_cnt}/30 illustrazioni")

    tab_front, tab_illus, tab_grid, tab_export = st.tabs(
        ["📄 Front Matter", "🎨 Aggiungi Illustrazione", "🗂 Griglia Pagine", "📥 Export PDF"]
    )

    # ── Tab 1: Front Matter ───────────────────────────────────────────────────
    with tab_front:
        st.subheader("Pagine Iniziali")
        st.caption("Aggiungi le pagine fisse di apertura al libro")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**📱 QR Code Page**")
            st.caption("Cattura lead: porta al bonus download")
            if st.button("Aggiungi QR Code Page", use_container_width=True):
                with st.spinner("Generando..."):
                    OUTPUT_SPECIAL.mkdir(parents=True, exist_ok=True)
                    path = OUTPUT_SPECIAL / "01_qr_code.png"
                    make_qr_page(st.session_state.qr_url).save(path, dpi=(OUTPUT_DPI, OUTPUT_DPI))
                    _add_page("special_qr", path)
                st.success("✓ QR Code Page aggiunta")

        with c2:
            st.markdown("**✍️ This Book Belongs To**")
            st.caption("Pagina personalizzabile per il regalo")
            if st.button("Aggiungi Frontespizio", use_container_width=True):
                with st.spinner("Generando..."):
                    path = OUTPUT_SPECIAL / "02_frontespizio.png"
                    make_frontespizio().save(path, dpi=(OUTPUT_DPI, OUTPUT_DPI))
                    _add_page("special_frontespizio", path)
                st.success("✓ Frontespizio aggiunto")

        with c3:
            st.markdown("**🎨 Test Your Colors**")
            st.caption("Griglia cerchi per testare i pennarelli")
            if st.button("Aggiungi Test Colors", use_container_width=True):
                with st.spinner("Generando..."):
                    path = OUTPUT_SPECIAL / "03_test_colors.png"
                    make_test_colors().save(path, dpi=(OUTPUT_DPI, OUTPUT_DPI))
                    _add_page("special_test_colors", path)
                st.success("✓ Test Colors aggiunta")

    # ── Tab 2: Add Illustration ───────────────────────────────────────────────
    with tab_illus:
        st.subheader("Genera Illustrazione")

        if not _get_api_key():
            st.error("⚠️ Servizio AI temporaneamente non disponibile. Contatta l'amministratore.")

        # Subject selector
        if niche_key == "astrology":
            subjects = [
                {
                    "key": sign,
                    "label": ZODIAC_CONFIG[sign]["en_name"],
                    **{k: ZODIAC_CONFIG[sign].get(k) for k in (
                        "glyph_unicode", "soggetto_kawaii", "thematic_prop", "scatter_elements"
                    ) if ZODIAC_CONFIG[sign].get(k) is not None},
                }
                for sign in SIGN_ORDER
            ]
        else:
            subjects = niche["subjects"]

        subject_labels = {s["label"]: s for s in subjects}
        selected_label = st.selectbox("Soggetto", list(subject_labels.keys()))
        subject_cfg    = subject_labels[selected_label]

        phrase = st.text_input(
            "Frase satirica",
            placeholder='Es. "Ok, ora torna coi piedi per terra e sii logico."',
            max_chars=120,
        )

        lang = st.selectbox("Lingua", ["it", "en", "de", "es", "fr", "pl"])

        col_btn, col_cost = st.columns([2, 1])
        with col_cost:
            st.caption("💰 Costo stimato: ~$0.04")

        with col_btn:
            generate_btn = st.button(
                "🎨 Genera Illustrazione",
                disabled=not phrase or not _get_api_key(),
                type="primary",
                use_container_width=True,
            )

        if generate_btn and phrase:
            with st.spinner(f"Generando '{selected_label}'… (~30 secondi)"):
                try:
                    path = _generate_illustration(
                        soggetto_kawaii=subject_cfg["soggetto_kawaii"],
                        glyph_unicode=subject_cfg.get("glyph_unicode", "★"),
                        thematic_prop=subject_cfg.get(
                            "thematic_prop", "a small thematic prop"
                        ),
                        scatter_elements=subject_cfg.get(
                            "scatter_elements",
                            "small 5-pointed stars, tiny hearts, small swirls",
                        ),
                        phrase=phrase,
                    )
                    # Add illustration + black separator
                    _add_page("illustration", path, {
                        "subject": subject_cfg["key"],
                        "phrase": phrase,
                        "lang": lang,
                    })
                    black_path = OUTPUT_SPECIAL / "black_separator.png"
                    if not black_path.exists():
                        make_black_page().save(black_path)
                    _add_page("special_black", black_path)

                    st.success(f"✓ Illustrazione generata: {path.name}")
                    # Mostriamo raw + final affiancati per debug visivo
                    raw_path = path.parent / path.name.replace("_final.png", "_raw.png")
                    col_a, col_b = st.columns(2)
                    if raw_path.exists():
                        with col_a:
                            st.caption("AI raw (prima del post-processing)")
                            st.image(str(raw_path), use_container_width=True)
                    with col_b:
                        st.caption("Finale (con testo)")
                        st.image(str(path), use_container_width=True)
                except Exception as e:
                    st.error(f"Errore generazione: {e}")

    # ── Tab 3: Page Grid ──────────────────────────────────────────────────────
    with tab_grid:
        pages = proj["pages"]
        if not pages:
            st.info("Nessuna pagina ancora. Aggiungi le pagine iniziali o genera un'illustrazione.")
        else:
            st.caption(f"{len(pages)} pagine totali nel libro")
            to_delete = []
            cols_per_row = 5

            for row_start in range(0, len(pages), cols_per_row):
                row_pages = pages[row_start:row_start + cols_per_row]
                cols = st.columns(cols_per_row)
                for col_offset, (col, page) in enumerate(zip(cols, row_pages)):
                    page_idx = row_start + col_offset  # posizione assoluta, sempre unica
                    with col:
                        st.markdown(f'<div class="page-thumb">', unsafe_allow_html=True)
                        thumb = _thumb(page["path"])
                        if thumb:
                            st.image(thumb, use_container_width=True)
                        else:
                            st.markdown("⚠️ File mancante")
                        pg_type = page["type"].replace("special_", "").replace("_", " ")
                        st.caption(f"#{page_idx+1} {pg_type}")
                        if st.button("🗑", key=f"del_{page_idx}", help="Elimina pagina"):
                            to_delete.append(page_idx)
                        st.markdown('</div>', unsafe_allow_html=True)

            if to_delete:
                for idx in sorted(to_delete, reverse=True):
                    proj["pages"].pop(idx)
                _save_project()
                st.rerun()

    # ── Tab 4: Export PDF — full 65-page KDP build pipeline ──────────────────
    with tab_export:
        st.subheader("Build libro KDP completo")
        st.caption("Pipeline in 3 step. Lo step 2 chiama l'API (~$1.20 per zodiacale).")

        on_disk_illus = sorted(OUTPUT_PAGES.glob("*_final.png")) if OUTPUT_PAGES.exists() else []
        special_files = sorted(OUTPUT_SPECIAL.glob("*.png")) if OUTPUT_SPECIAL.exists() else []

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Special pages",   f"{len(special_files)}/6")
        col2.metric("Illustrazioni",   f"{len(on_disk_illus)}/30")
        col3.metric("Pagine progetto", len(proj["pages"]))
        col4.metric("Formato",         "8.5\" × 11\"")

        st.markdown("##### Step 1 · Genera special pages")
        st.caption("QR, Frontespizio, Test Colors, Black separator, Review, Collection. Zero costo API.")
        s1a, s1b = st.columns([2, 1])
        qr_url = s1a.text_input("URL QR", value=st.session_state.get("qr_url",
                                "https://thedailyburnoutpress.com/bonus"),
                                key="export_qr_url")
        if s1b.button("🪄 Genera 6 special pages", type="secondary", use_container_width=True,
                      key="export_step1"):
            with st.spinner("Generando…"):
                try:
                    saved = _build_all_special_pages(qr_url)
                    st.session_state["qr_url"] = qr_url
                    st.success(f"✅ {len(saved)} file in {OUTPUT_SPECIAL}/")
                except Exception as e:
                    st.error(f"Errore: {e}")

        st.markdown("##### Step 2 · Batch generate 30 illustrazioni zodiacali")
        s2a, s2b, s2c = st.columns([1, 1, 1])
        lang = s2a.selectbox("Lingua", ["it", "en"], key="export_lang")
        threshold = s2b.slider("Threshold B/W", 100, 220, BINARIZE_THR, 5, key="export_thr")
        s2c.metric("Costo stimato", f"~${30 * 0.04:.2f}")
        if niche_key != "astrology":
            st.info("Batch automatico disponibile solo per la nicchia **Astrology** (usa FRASI). "
                    "Per altre nicchie usa Book Builder o Studio Mode.")
        elif st.button("⚡ Genera 30 illustrazioni",
                       type="primary", use_container_width=True,
                       disabled=not _get_api_key(), key="export_step2"):
            jobs: list[tuple[str, str]] = []
            for sign in SIGN_ORDER:
                for phrase in FRASI.get(sign, {}).get(lang, []):
                    jobs.append((sign, phrase))
            jobs = jobs[:30]
            prog = st.progress(0.0, text=f"0/{len(jobs)}")
            done, errs = 0, []
            for i, (sign, phrase) in enumerate(jobs, 1):
                try:
                    path = _generate_zodiac_illustration(sign, phrase, i, threshold=threshold)
                    done += 1
                    prog.progress(i / len(jobs),
                                  text=f"{i}/{len(jobs)} · {sign} · {Path(path).name}")
                except Exception as e:
                    errs.append(f"{sign}/{phrase}: {e}")
                    prog.progress(i / len(jobs),
                                  text=f"{i}/{len(jobs)} · {sign} · ERROR")
            prog.empty()
            if done == len(jobs):
                st.success(f"✅ {done}/{len(jobs)} generate")
            else:
                st.warning(f"⚠ {done}/{len(jobs)} ok · {len(errs)} errori")
                with st.expander("Dettagli errori"):
                    st.code("\n".join(errs))

        st.markdown("##### Step 3 · Assembla PDF KDP 65 pagine")
        st.caption("Usa output/special/* + output/pages/* (round-robin 30 ill. + 2 back matter). "
                   "QC: 65 pp esatte, 8.5×11\" @ 300 DPI.")
        s3a, s3b = st.columns([2, 1])
        out_name = s3a.text_input("Nome file output", value="zodiacale_v1.pdf",
                                  key="export_out_name")
        if s3b.button("📕 Assembla 65 pp", type="primary", use_container_width=True,
                      key="export_step3"):
            try:
                with st.spinner("Assemblando…"):
                    pdf_bytes, qc = _assemble_full_book_pdf(lang=lang, output_name=out_name)
                badge = "✅ OK" if qc["ok"] else f"⚠ {qc['actual']}/{qc['target']}"
                st.success(f"{badge} · {len(pdf_bytes)/1e6:.1f} MB · output/final/{Path(out_name).name}")
                if qc["issues"]:
                    with st.expander(f"QC issues ({len(qc['issues'])})"):
                        for issue in qc["issues"][:20]:
                            st.text(f"- {issue}")
                st.download_button(
                    f"⬇️ Scarica {Path(out_name).name}", pdf_bytes,
                    file_name=Path(out_name).name, mime="application/pdf",
                    type="primary", key="export_dl_full",
                )
            except Exception as e:
                st.error(f"Errore: {e}")

        st.divider()
        with st.expander("📥 Draft PDF dalla session (pagine nel Book Builder)"):
            pages = proj["pages"]
            if not pages:
                st.info("Nessuna pagina nella session corrente.")
            elif st.button("Genera draft", key="export_draft"):
                with st.spinner("Assemblando draft…"):
                    pdf_bytes = _assemble_pdf_bytes()
                if pdf_bytes:
                    niche_name = NICHES.get(niche_key, {}).get("name", niche_key).replace(" ", "_")
                    filename = f"kdp_{niche_name}_DRAFT.pdf"
                    st.download_button(
                        f"⬇️ Scarica {filename}", pdf_bytes,
                        file_name=filename, mime="application/pdf",
                        key="export_dl_draft",
                    )
                    st.success(f"Draft: {len(pdf_bytes)/1e6:.1f} MB · {len(pages)} pagine")
                else:
                    st.error("Errore.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: STUDIO MODE
# ══════════════════════════════════════════════════════════════════════════════

TEXT_STYLES: dict[str, str] = {
    "Banner/Ribbon":        "with a large blank decorative banner or ribbon spanning across the bottom of the scene, completely empty white space inside for text",
    "Cartello (a mano)":    "with a character holding up a large blank wooden sign or cardboard sign, the sign surface completely empty white for text",
    "Schermo (PC/Phone)":   "with a computer monitor or phone screen prominently showing a completely blank white rectangle, clearly meant for text",
    "Fumetto":              "with a large empty speech bubble or thought bubble from the main character, the bubble interior completely blank white",
    "Tazza/Mug":            "with a large mug or coffee cup facing the viewer, its surface showing a blank white rectangular label area for text",
    "T-Shirt":              "with the main character wearing a t-shirt that has a completely blank white rectangular area on the front",
    "Poster sul muro":      "with a framed blank white poster visible on the wall behind the main subject, clearly meant for text",
    "Pergamena":            "with an unrolled blank parchment scroll in the foreground, its surface completely empty white for text",
    "Lettering decorativo": "with an ornate decorative empty frame at the bottom of the illustration, surrounded by flourishes but empty inside",
}

BORDER_STYLES = {
    "kawaii-tarot":  "kawaii tarot card border, ornate but clean, double line with corner ornaments",
    "art-deco":      "art-deco geometric border, symmetric stepped chevrons and fan motifs",
    "vintage":       "vintage etched border, fine engraved filigree, classical scrollwork",
    "minimal":       "thin minimal double-line border, no ornaments, generous whitespace",
    "none":          "",
}

LAYOUTS = {
    "top70-bottom30":   "TOP 70% kawaii illustration / BOTTOM 30% completely empty white rectangle for text",
    "full-page":        "single full-bleed illustration filling the entire page edge-to-edge",
    "center-piece":     "single centered medallion illustration with generous white margins on all sides",
    "split-vertical":   "LEFT 50% illustration / RIGHT 50% completely empty white rectangle for text",
    "split-horizontal": "TOP 50% illustration / BOTTOM 50% completely empty white rectangle for text",
}

OUTPUT_MODES    = ("B&W puro", "Grayscale", "RGB color")
PIPELINE_ORDERS = ("upscale_then_binarize", "binarize_then_upscale")
SIZE_OPTIONS    = ("1024x1024", "1024x1536", "1536x1024")
QUALITY_OPTIONS = ("low", "medium", "high")
MODEL_OPTIONS   = ("gpt-image-1",)

# Approximate OpenAI list-price (USD per image) — UI display only
COST_TABLE = {
    ("gpt-image-1", "low"):    {"1024x1024": 0.011, "1024x1536": 0.016, "1536x1024": 0.016},
    ("gpt-image-1", "medium"): {"1024x1024": 0.042, "1024x1536": 0.063, "1536x1024": 0.063},
    ("gpt-image-1", "high"):   {"1024x1024": 0.167, "1024x1536": 0.250, "1536x1024": 0.250},
}

STUDIO_PRESETS_DIR = OUTPUT_BASE / "studio_presets"
STUDIO_OUT_DIR     = OUTPUT_BASE / "studio"
COVER_OUT_DIR      = OUTPUT_BASE / "cover"


# ── Studio session-state init ─────────────────────────────────────────────────

def _studio_state() -> dict:
    if "studio" not in st.session_state:
        st.session_state["studio"] = {
            "results": [],
            "last_prompt": "",
        }
    return st.session_state["studio"]


def _slugify(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", (s or "").strip()).strip("_").lower()
    return (s[:maxlen] or "untitled")


def _estimate_cost(model: str, quality: str, size: str, n: int) -> float:
    return COST_TABLE.get((model, quality), {}).get(size, 0.05) * max(1, n)


def _refund_quota_slot() -> None:
    """Decrement today's persisted quota by 1 (after a failed API call)."""
    today = datetime.now().date().isoformat()
    quota = _load_quota()
    quota[today] = max(0, int(quota.get(today, 0)) - 1)
    _save_quota(quota)
    st.session_state["img_quota_count"] = max(0, st.session_state.get("img_quota_count", 0) - 1)


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_template_prompt(
    *, layout: str, border_style: str, corner_sym: str, side_sym: str,
    subject: str, kawaii_rules: bool, anti_gray: bool, custom_rules: str,
    text_style_phrase: str, drop_bottom_empty: bool,
) -> str:
    """Compose a master prompt from togglable sections."""
    parts: list[str] = []
    parts.append(
        "Black and white kawaii coloring book illustration page. "
        "Pure black outlines on pure white background. Bold uniform linework throughout."
    )

    layout_text = LAYOUTS.get(layout, LAYOUTS["top70-bottom30"])
    if drop_bottom_empty and layout == "top70-bottom30":
        layout_text = (
            "single full-page illustration with the text-container element "
            "integrated into the composition (see MAIN ILLUSTRATION below)"
        )
    parts.append(f"PAGE LAYOUT (critical):\n{layout_text}")

    if border_style and border_style != "none":
        parts.append(
            "DECORATIVE BORDER (must surround the entire page):\n"
            f"- Style: {BORDER_STYLES[border_style]}\n"
            f"- Four corners: large {corner_sym} filling each corner space\n"
            f"- All four sides: {side_sym} repeated at regular intervals along the side\n"
            "- Border width: approximately 8% of page width on each side"
        )

    main = f"MAIN ILLUSTRATION:\n- Subject: {subject}"
    if text_style_phrase:
        main += f"\n- Text-container: {text_style_phrase}"
    if kawaii_rules:
        main += (
            "\n- Style: chibi kawaii, big cute round eyes, simple happy expression, rounded shapes"
            "\n- Background: pure white with at most 4 small decorative elements scattered"
        )
    parts.append(main)

    rules: list[str] = ["NO text, letters, or numbers anywhere in the image"]
    if anti_gray:
        rules += ["NO gray pixels anywhere", "NO shading, NO gradients, NO textures"]
    if custom_rules.strip():
        rules += [r.strip() for r in custom_rules.splitlines() if r.strip()]
    parts.append("ABSOLUTE RULES:\n- " + "\n- ".join(rules))

    return "\n\n".join(parts)


# ── Preset I/O ────────────────────────────────────────────────────────────────

def _list_presets() -> list[str]:
    STUDIO_PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.stem for p in STUDIO_PRESETS_DIR.glob("*.json"))


def _save_preset(name: str, payload: dict) -> Path:
    STUDIO_PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    safe = _slugify(name)
    path = STUDIO_PRESETS_DIR / f"{safe}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _load_preset(name: str) -> dict:
    path = STUDIO_PRESETS_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


# ── Smart text injection: detect a blank white region and write inside it ─────

def _largest_white_region(arr_l: np.ndarray, white_thr: int = 245):
    """Find bounding box of the largest connected white blob.

    Pure numpy/Pillow — no scipy/cv2. Adequate for the well-separated white
    containers that gpt-image-1 produces (banner, scroll, mug-label, etc.).
    Returns (x0, y0, x1, y1) or None.
    """
    h, w = arr_l.shape
    mask = arr_l >= white_thr

    scale = max(1, max(w, h) // 512)
    if scale > 1:
        mask = mask[::scale, ::scale]
    mh, mw = mask.shape

    labels = np.zeros(mask.shape, dtype=np.int32)
    next_id = 1
    parent: dict = {}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for y in range(mh):
        for x in range(mw):
            if not mask[y, x]:
                continue
            up   = labels[y - 1, x] if y > 0 else 0
            left = labels[y, x - 1] if x > 0 else 0
            if up and left:
                lab = min(up, left)
                labels[y, x] = lab
                union(int(up), int(left))
            elif up or left:
                labels[y, x] = up or left
            else:
                parent[next_id] = next_id
                labels[y, x] = next_id
                next_id += 1
    if next_id == 1:
        return None

    flat = labels.ravel()
    roots = np.zeros_like(flat)
    cache: dict = {}
    for i, v in enumerate(flat):
        v = int(v)
        if v == 0:
            continue
        r = cache.get(v)
        if r is None:
            r = find(v)
            cache[v] = r
        roots[i] = r
    roots = roots.reshape(labels.shape)

    best = (0, (0, 0, 0, 0))
    for rid in np.unique(roots):
        if rid == 0:
            continue
        ys, xs = np.where(roots == rid)
        area = ys.size
        touches_all_edges = (ys.min() == 0 and ys.max() == mh - 1
                             and xs.min() == 0 and xs.max() == mw - 1)
        if touches_all_edges:
            continue
        if area > best[0]:
            best = (area, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))

    if best[0] == 0:
        return None
    x0, y0, x1, y1 = best[1]
    inset = 4
    return (max(0, x0 * scale + inset),
            max(0, y0 * scale + inset),
            min(w - 1, x1 * scale - inset),
            min(h - 1, y1 * scale - inset))


def inject_text_in_zone(img: Image.Image, phrase: str) -> Image.Image:
    """Detect the largest empty white region in the AI output and write inside.
    Falls back to legacy bottom-band inject_text() if no zone is found."""
    if not phrase:
        return img
    arr_l = np.array(img.convert("L"))
    box = _largest_white_region(arr_l)
    if box is None:
        return inject_text(img, phrase)

    from generate_page import _load_font, _wrap_to_width
    x0, y0, x1, y1 = box
    zone_w = max(40, x1 - x0)
    zone_h = max(20, y1 - y0)

    draw = ImageDraw.Draw(img)
    h_pad = int(zone_w * 0.05)
    max_w = zone_w - 2 * h_pad
    target_h = int(zone_h * 0.80)

    best = None
    for fs in range(int(zone_h * 0.9), 14, -3):
        font = _load_font(fs)
        lines = _wrap_to_width(draw, phrase, font, max_w)
        line_gap = int(fs * 0.25)
        line_h = draw.textbbox((0, 0), "Ay", font=font)[3]
        blk_h = line_h * len(lines) + line_gap * (len(lines) - 1)
        max_lw = max(draw.textbbox((0, 0), ln, font=font)[2] for ln in lines)
        if blk_h <= target_h and max_lw <= max_w:
            best = (font, lines, line_gap, line_h, blk_h)
            break
    if best is None:
        font = _load_font(18)
        lines = _wrap_to_width(draw, phrase, font, max_w)
        line_h = draw.textbbox((0, 0), "Ay", font=font)[3]
        best = (font, lines, 6, line_h, line_h * len(lines) + 6 * (len(lines) - 1))

    font, lines, line_gap, line_h, blk_h = best
    y = y0 + (zone_h - blk_h) // 2
    for line in lines:
        lw = draw.textbbox((0, 0), line, font=font)[2]
        x = x0 + (zone_w - lw) // 2
        draw.text((x, y), line, font=font, fill=(0, 0, 0))
        y += line_h + line_gap
    return img


# ── Quota-safe API call (refunds on failure) ──────────────────────────────────

def _generate_with_refund(prompt: str, *, model: str, size: str,
                          quality: str, n: int) -> list[Image.Image]:
    from openai import OpenAI
    import base64
    import urllib.request
    from urllib.parse import urlparse
    from io import BytesIO

    client = OpenAI(api_key=_get_api_key() or None)
    out: list[Image.Image] = []
    for _ in range(n):
        _check_image_quota()
        try:
            resp = client.images.generate(
                model=model, prompt=prompt, size=size, quality=quality, n=1,
            )
            item = resp.data[0]
            if getattr(item, "b64_json", None):
                out.append(Image.open(BytesIO(base64.b64decode(item.b64_json))).convert("RGB"))
            elif getattr(item, "url", None):
                parsed = urlparse(item.url)
                if parsed.scheme != "https" or not parsed.hostname or not (
                    parsed.hostname.endswith(".openai.com")
                    or parsed.hostname.endswith(".oaiusercontent.com")
                    or parsed.hostname.endswith(".azure.com")
                ):
                    raise RuntimeError(f"Refusing to fetch image from unexpected host: {parsed.hostname}")
                with urllib.request.urlopen(item.url, timeout=30) as r:
                    out.append(Image.open(BytesIO(r.read())).convert("RGB"))
            else:
                raise RuntimeError("OpenAI response: no b64_json or url found.")
        except Exception:
            _refund_quota_slot()
            raise
    return out


# ── Pipeline runner with all toggles ──────────────────────────────────────────

def _run_pipeline(
    raw: Image.Image, *, threshold: int, output_mode: str, pipeline_order: str,
    do_white_zone: bool, phrase: str, do_inject: bool, use_zone_detector: bool,
    out_w: int, out_h: int,
) -> tuple[Image.Image, dict]:
    """Apply the configured post-processing chain. QC computed AFTER everything."""
    img = raw

    if pipeline_order == "upscale_then_binarize":
        if img.size != (out_w, out_h):
            img = img.resize((out_w, out_h), Image.BICUBIC)
        if output_mode == "B&W puro":
            img = binarize(img, threshold)
        elif output_mode == "Grayscale":
            img = img.convert("L").convert("RGB")
        if do_white_zone:
            img = enforce_white_text_zone(img)
    else:  # binarize_then_upscale (legacy)
        if output_mode == "B&W puro":
            img = binarize(img, threshold)
        elif output_mode == "Grayscale":
            img = img.convert("L").convert("RGB")
        if do_white_zone:
            img = enforce_white_text_zone(img)
        if img.size != (out_w, out_h):
            img = img.resize((out_w, out_h), Image.BICUBIC)

    if do_inject and phrase:
        img = inject_text_in_zone(img, phrase) if use_zone_detector else inject_text(img, phrase)

    arr = np.array(img.convert("L"))
    qc = {
        "white_pct":   float((arr > 200).mean() * 100),
        "gray_pixels": int(((arr > 10) & (arr < 245)).sum()),
    }
    qc["kdp_ok"] = (output_mode != "B&W puro") or (qc["gray_pixels"] < 1000)
    return img, qc


# ── UI ────────────────────────────────────────────────────────────────────────

def page_studio_mode() -> None:
    st.title("🎨 Studio Mode")
    st.caption("Controllo estremo: prompt, layout, pipeline, QC")
    if not _get_api_key():
        st.error("⚠️ Servizio AI temporaneamente non disponibile. Contatta l'amministratore.")

    state = _studio_state()
    tab_quick, tab_custom, tab_advanced, tab_cover = st.tabs(
        ["⚡ Quick", "🧱 Custom", "🔧 Advanced", "📕 Cover"]
    )

    def _api_param_block(prefix: str) -> dict:
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        model   = c1.selectbox("Model",   MODEL_OPTIONS,   key=f"{prefix}_model")
        size    = c2.selectbox("Size",    SIZE_OPTIONS,    index=1, key=f"{prefix}_size")
        quality = c3.selectbox("Quality", QUALITY_OPTIONS, index=2, key=f"{prefix}_quality")
        n_var   = c4.number_input("Variants", 1, 4, 1, key=f"{prefix}_n")
        cost = _estimate_cost(model, quality, size, int(n_var))
        st.caption(f"💰 Costo stimato: ~${cost:.3f}  ·  Quota oggi: "
                   f"{st.session_state.get('img_quota_count', 0)}/{DAILY_IMAGE_CAP}")
        return {"model": model, "size": size, "quality": quality, "n": int(n_var)}

    def _pipeline_block(prefix: str, *, default_inject: bool = True) -> dict:
        with st.expander("Post-processing", expanded=False):
            c1, c2 = st.columns(2)
            threshold   = c1.slider("Threshold B/W", 100, 220, BINARIZE_THR, 5, key=f"{prefix}_thr")
            order       = c2.selectbox("Pipeline order", PIPELINE_ORDERS, key=f"{prefix}_order")
            output_mode = c1.selectbox("Output mode", OUTPUT_MODES, key=f"{prefix}_outmode")
            do_white    = c2.checkbox("enforce_white_text_zone", value=False, key=f"{prefix}_wz")
            do_inj      = c1.checkbox("Inject phrase", value=default_inject, key=f"{prefix}_inj")
            use_zone    = c2.checkbox("Detect white zone (smart)", value=True, key=f"{prefix}_zone")
            c3, c4 = st.columns(2)
            out_w = c3.number_input("Output W", 512, 6000, KDP_W, 50, key=f"{prefix}_w")
            out_h = c4.number_input("Output H", 512, 6000, KDP_H, 50, key=f"{prefix}_h")
            return {
                "threshold": int(threshold), "pipeline_order": order, "output_mode": output_mode,
                "do_white_zone": do_white, "do_inject": do_inj, "use_zone_detector": use_zone,
                "out_w": int(out_w), "out_h": int(out_h),
            }

    def _persist_and_render(raw_imgs: list, prompt: str, pipe: dict,
                            phrase: str, niche_slug: str, dest_book: bool) -> None:
        STUDIO_OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = []
        for i, raw in enumerate(raw_imgs):
            img, qc = _run_pipeline(raw, phrase=phrase, **pipe)
            slug = _slugify(phrase or "studio")
            path = STUDIO_OUT_DIR / f"{niche_slug}_{ts}_{i+1}_{slug}.png"
            img.save(path, dpi=(OUTPUT_DPI, OUTPUT_DPI))
            results.append({"path": str(path), "prompt": prompt, **qc})
        state["results"] = results
        state["last_prompt"] = prompt
        if dest_book and results:
            _add_page("illustration", Path(results[0]["path"]),
                      {"phrase": phrase, "subject": "studio"})

    def _render_results() -> None:
        if not state["results"]:
            return
        st.markdown("### Risultati")
        cols = st.columns(min(4, len(state["results"])))
        for i, (col, r) in enumerate(zip(cols, state["results"])):
            with col:
                t = _thumb(r["path"])
                if t:
                    st.image(t, use_container_width=True)
                badge = "✅" if r["kdp_ok"] else "⚠️"
                st.caption(f"{badge} grigi: {r['gray_pixels']:,} · bianco {r['white_pct']:.0f}%")
                with open(r["path"], "rb") as f:
                    st.download_button("⬇️ PNG", f.read(),
                                       file_name=Path(r["path"]).name,
                                       mime="image/png", key=f"dl_{i}_{Path(r['path']).stem}")

    # ─── TAB 1: QUICK ─────────────────────────────────────────────────────────
    with tab_quick:
        st.subheader("Quick — i 9 stili classici, ora con text-zone detection")
        scene = st.text_area("Scena", height=80, key="q_scene",
            placeholder="exhausted office worker surrounded by paperwork and coffee cups")
        phrase = st.text_input("Frase satirica", max_chars=120, key="q_phrase")
        text_style = st.selectbox("Stile testo", list(TEXT_STYLES.keys()), key="q_style")
        fill = st.text_input("Elementi extra", key="q_fill",
                             placeholder="coffee cups, papers, staplers")
        api = _api_param_block("q")
        pipe = _pipeline_block("q", default_inject=True)
        dest = st.radio("Destinazione", ["📚 Book Builder", "🖼 output/studio/"],
                        horizontal=True, key="q_dest")
        if st.button("🎨 Genera", type="primary", key="q_btn",
                     disabled=not scene or not _get_api_key()):
            subj = f"{scene}, {TEXT_STYLES[text_style]}."
            if fill:
                subj += f" Include: {fill}."
            prompt = _build_template_prompt(
                layout="top70-bottom30", border_style="kawaii-tarot",
                corner_sym="decorative kawaii corner ornament",
                side_sym="small kawaii thematic symbol",
                subject=subj, kawaii_rules=True, anti_gray=True, custom_rules="",
                text_style_phrase=TEXT_STYLES[text_style], drop_bottom_empty=True,
            )
            try:
                with st.spinner(f"Generando {api['n']} variante/i…"):
                    raws = _generate_with_refund(prompt, **api)
                niche_key = st.session_state.project.get("niche") or "studio"
                _persist_and_render(raws, prompt, pipe, phrase,
                                    _slugify(niche_key), "Book" in dest)
            except Exception as e:
                st.error(f"Errore: {e}")
        _render_results()

    # ─── TAB 2: CUSTOM (template builder) ────────────────────────────────────
    with tab_custom:
        st.subheader("Custom — costruisci il prompt da sezioni")
        c1, c2, c3 = st.columns([2, 2, 1])
        presets = _list_presets()
        sel = c1.selectbox("Preset", ["—"] + presets, key="c_preset_sel")
        if sel != "—" and c2.button("📂 Carica preset", key="c_load"):
            data = _load_preset(sel)
            for k, v in data.items():
                st.session_state[f"c_{k}"] = v
            st.rerun()
        preset_name = c2.text_input("Nome preset", key="c_preset_name")
        if c3.button("💾 Salva", key="c_save", disabled=not preset_name):
            keys = ["layout", "border", "corner", "side", "subject", "kawaii",
                    "antigray", "rules", "style", "phrase", "fill"]
            payload = {k: st.session_state.get(f"c_{k}") for k in keys}
            p = _save_preset(preset_name, payload)
            st.success(f"Salvato: {p.name}")

        layout = st.selectbox("Layout", list(LAYOUTS.keys()), key="c_layout")
        b1, b2, b3 = st.columns(3)
        border = b1.selectbox("Border style", list(BORDER_STYLES.keys()), key="c_border")
        corner = b2.text_input("Corner symbol", value="decorative kawaii ornament", key="c_corner")
        side   = b3.text_input("Side symbol",   value="small kawaii symbol", key="c_side")
        subject = st.text_area("Subject", height=80, key="c_subject")
        s1, s2 = st.columns(2)
        kawaii = s1.checkbox("Kawaii style rules", value=True, key="c_kawaii")
        antigray = s2.checkbox("Anti-gray rules",  value=True, key="c_antigray")
        style = st.selectbox("Text-style integration", ["(none)"] + list(TEXT_STYLES.keys()),
                             key="c_style")
        rules = st.text_area("Custom rules (one per line)", height=70, key="c_rules")
        phrase = st.text_input("Frase satirica", max_chars=120, key="c_phrase")
        api = _api_param_block("c")
        pipe = _pipeline_block("c", default_inject=True)
        dest = st.radio("Destinazione", ["📚 Book Builder", "🖼 output/studio/"],
                        horizontal=True, key="c_dest")

        ts_phrase = TEXT_STYLES[style] if style in TEXT_STYLES else ""
        prompt_preview = _build_template_prompt(
            layout=layout, border_style=border, corner_sym=corner, side_sym=side,
            subject=subject or "(empty subject)", kawaii_rules=kawaii,
            anti_gray=antigray, custom_rules=rules, text_style_phrase=ts_phrase,
            drop_bottom_empty=bool(ts_phrase),
        )
        with st.expander("Preview prompt", expanded=False):
            st.code(prompt_preview)

        if st.button("🎨 Genera", type="primary", key="c_btn",
                     disabled=not subject or not _get_api_key()):
            try:
                with st.spinner(f"Generando {api['n']} variante/i…"):
                    raws = _generate_with_refund(prompt_preview, **api)
                niche_key = st.session_state.project.get("niche") or "studio"
                _persist_and_render(raws, prompt_preview, pipe, phrase,
                                    _slugify(niche_key), "Book" in dest)
            except Exception as e:
                st.error(f"Errore: {e}")
        _render_results()

    # ─── TAB 3: ADVANCED (raw prompt edit) ───────────────────────────────────
    with tab_advanced:
        st.subheader("Advanced — full prompt + tutte le toggles")
        if "a_prompt" not in st.session_state:
            st.session_state["a_prompt"] = MASTER_PROMPT_TEMPLATE.format(
                glyph_unicode="★",
                soggetto_kawaii="(describe your subject here)",
                thematic_prop="(describe a thematic prop near the subject)",
                scatter_elements="small 5-pointed stars, tiny hearts, small swirls",
            )
        prompt = st.text_area("Master prompt", height=320, key="a_prompt")
        phrase = st.text_input("Frase satirica (opzionale)", max_chars=120, key="a_phrase")
        api = _api_param_block("a")
        pipe = _pipeline_block("a", default_inject=False)
        out_tpl = st.text_input("Filename template",
                                value="{niche}_{ts}_{slug}", key="a_tpl",
                                help="placeholders: {niche} {ts} {slug}")
        dest = st.radio("Destinazione",
                        ["📚 Book Builder", "🖼 output/studio/", "🖼 output/cover/"],
                        horizontal=True, key="a_dest")
        if st.button("🎨 Genera", type="primary", key="a_btn",
                     disabled=not prompt.strip() or not _get_api_key()):
            try:
                with st.spinner(f"Generando {api['n']} variante/i…"):
                    raws = _generate_with_refund(prompt, **api)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                niche_slug = _slugify(st.session_state.project.get("niche") or "studio")
                slug = _slugify(phrase or "studio")
                target = COVER_OUT_DIR if "cover" in dest else STUDIO_OUT_DIR
                target.mkdir(parents=True, exist_ok=True)
                results = []
                for i, raw in enumerate(raws):
                    img, qc = _run_pipeline(raw, phrase=phrase, **pipe)
                    fname = (out_tpl.format(niche=niche_slug, ts=ts, slug=slug)
                             + (f"_{i+1}" if len(raws) > 1 else "")
                             + ".png")
                    p = target / fname
                    img.save(p, dpi=(OUTPUT_DPI, OUTPUT_DPI))
                    results.append({"path": str(p), "prompt": prompt, **qc})
                state["results"] = results
                state["last_prompt"] = prompt
                if "Book" in dest and results:
                    _add_page("illustration", Path(results[0]["path"]),
                              {"phrase": phrase, "subject": "studio_advanced"})
            except Exception as e:
                st.error(f"Errore: {e}")
        _render_results()

    # ─── TAB 4: COVER (delegates to cover_builder) ───────────────────────────
    with tab_cover:
        st.subheader("Cover Builder")
        try:
            import cover_builder
            if hasattr(cover_builder, "render_cover_ui"):
                cover_builder.render_cover_ui(_get_api_key, _check_image_quota,
                                              _generate_with_refund, _run_pipeline)
            else:
                st.info("`cover_builder.py` trovato ma manca `render_cover_ui()`.")
        except ImportError:
            st.info(
                "Modulo `cover_builder.py` non disponibile. "
                "Per ora usa la tab **Advanced** con destinazione `output/cover/` "
                "e size `1536x1024`."
            )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MARKETING
# ══════════════════════════════════════════════════════════════════════════════

def page_marketing() -> None:
    st.title("📈 Marketing Funnel")

    tab_kw, tab_lp, tab_qr, tab_email = st.tabs([
        "🔍 Keyword Extractor",
        "🌐 Landing Page",
        "📱 QR URL Config",
        "✉️ Email (Coming Soon)",
    ])

    # ── Keyword Extractor ─────────────────────────────────────────────────────
    with tab_kw:
        st.subheader("Amazon Keyword Extractor")
        st.caption("Estrae long-tail keywords ad alto intento d'acquisto dall'autosuggest Amazon")

        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            seed = st.text_input("Keyword Seed", placeholder='Es. "adult coloring book zodiac"')
        with col2:
            market = st.selectbox("Mercato", list(MARKETS.keys()))
        with col3:
            depth = st.selectbox("Profondità", [1, 2], help="2 = espansione alfabetica (~26× più keywords)")

        if st.button("🔍 Estrai Keywords", disabled=not seed, type="primary"):
            with st.spinner(f"Interrogando Amazon {market}…"):
                try:
                    keywords = expand_keywords(seed, market, depth)
                    st.session_state["kw_results"] = keywords
                except Exception as e:
                    st.error(f"Errore: {e}")

        results = st.session_state.get("kw_results", [])
        if results:
            st.success(f"✅ Trovate {len(results)} keywords")
            kw_text = "\n".join(results)
            st.text_area("Keywords estratte", kw_text, height=300)
            st.download_button(
                "⬇️ Scarica TXT",
                data=kw_text,
                file_name=f"keywords_{seed[:20].replace(' ','_')}_{market}.txt",
                mime="text/plain",
            )

    # ── Landing Page ──────────────────────────────────────────────────────────
    with tab_lp:
        st.subheader("Landing Page Generator")
        st.caption("Genera un bundle HTML GDPR-compliant pronto per hosting (Netlify, Vercel, GitHub Pages)")

        col1, col2 = st.columns(2)
        with col1:
            lp_title     = st.text_input("Titolo Libro", value="Zodiaco Esaurito")
            lp_headline  = st.text_input(
                "Headline",
                value="Hai comprato il libro. Ora sblocca il tuo bonus riservato.",
            )
            lp_publisher = st.text_input("Editore", value="The Daily Burnout Press")
        with col2:
            lp_primary  = st.color_picker("Colore Primario", value="#1a1a2e")
            lp_accent   = st.color_picker("Colore Accento",  value="#e94560")
            lp_dark     = st.toggle("Dark Mode", value=True)
            lp_qr_url   = st.text_input("URL QR Code", value=st.session_state.qr_url)

        if st.button("🌐 Genera Landing Page", type="primary"):
            with st.spinner("Generando bundle HTML…"):
                zip_bytes = generate_landing_page(
                    title=lp_title,
                    headline=lp_headline,
                    primary_color=lp_primary,
                    accent_color=lp_accent,
                    dark_mode=lp_dark,
                    qr_url=lp_qr_url,
                    publisher=lp_publisher,
                )
            st.success(f"✅ Bundle generato: {len(zip_bytes)/1024:.1f} KB")
            st.download_button(
                label="⬇️ Scarica ZIP (index.html + thank-you + privacy + CSS)",
                data=zip_bytes,
                file_name=f"landing_{lp_title[:20].replace(' ','_')}.zip",
                mime="application/zip",
                type="primary",
            )
            st.info(
                "📦 Il ZIP contiene: `index.html` · `thank-you.html` · `privacy.html` · `style.css`\n\n"
                "Carica i file su **Netlify** (trascina e rilascia) o **GitHub Pages** per averli online in 2 minuti."
            )

    # ── QR URL Config ─────────────────────────────────────────────────────────
    with tab_qr:
        st.subheader("Configurazione URL QR Code")
        st.caption("L'URL stampato nei libri — deve puntare alla tua landing page")

        base_url = st.text_input("URL Landing Page", value=st.session_state.qr_url)

        st.markdown("**Parametri UTM (tracking automatico)**")
        col1, col2 = st.columns(2)
        with col1:
            niche_key = st.session_state.project.get("niche", "zodiac")
            utm_source = st.text_input("utm_source", value="kdp_book")
            utm_medium = st.text_input("utm_medium", value="print_qr")
        with col2:
            utm_campaign = st.text_input("utm_campaign", value=niche_key or "zodiac")
            utm_content  = st.text_input("utm_content",  value="v1")

        use_utm = st.toggle("Aggiungi parametri UTM all'URL", value=True)

        if use_utm:
            full_url = (
                f"{base_url}?utm_source={utm_source}"
                f"&utm_medium={utm_medium}"
                f"&utm_campaign={utm_campaign}"
                f"&utm_content={utm_content}"
            )
        else:
            full_url = base_url

        st.code(full_url)

        if st.button("💾 Salva URL nei Settings", type="primary"):
            st.session_state.qr_url = full_url
            st.success(f"✅ URL salvato: {full_url}")

        # QR preview
        try:
            import qrcode
            qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=2)
            qr.add_data(full_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            buf = io.BytesIO()
            qr_img.save(buf, format="PNG")
            st.image(buf.getvalue(), caption="Preview QR Code", width=200)
        except ImportError:
            st.caption("Installa qrcode[pil] per il preview: `pip install qrcode[pil]`")

    # ── Email Automation ──────────────────────────────────────────────────────
    with tab_email:
        st.subheader("✉️ Email Automation")
        st.info(
            "**In sviluppo.** Integrazione pianificata con Brevo/MailerLite.\n\n"
            "Sequenza automatica in arrivo:\n"
            "- Giorno 1: Consegna bonus + benvenuto\n"
            "- Giorno 2: Storia ironica sul burnout\n"
            "- Giorno 3: Invito recensione Amazon\n"
            "- Giorno 4: Pitch Bundle PDF ($14.99)\n"
            "- Giorno 5: Pitch Merchandise\n\n"
            "File da implementare: `email_sequence.py`"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR + MAIN
# ══════════════════════════════════════════════════════════════════════════════

def _check_password() -> bool:
    """Single-password gate. Bypassed if APP_PASSWORD env var is not set
    (utile in dev locale). In produzione (Railway) impostare APP_PASSWORD."""
    expected = os.environ.get("APP_PASSWORD", "").strip()
    if not expected:
        return True  # No password configured → open (dev mode)

    if st.session_state.get("authenticated"):
        return True

    # Login screen
    st.markdown(
        "<div style='text-align:center; padding:3em 1em 1em 1em;'>"
        "<h1>📚 KDP Publishing House</h1>"
        "<p style='color:#666;'>Accesso riservato</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        with st.form("login", clear_on_submit=False):
            pwd = st.text_input("Password", type="password",
                                placeholder="Inserisci la password")
            ok = st.form_submit_button("Entra", use_container_width=True)
        if ok:
            if pwd == expected:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Password errata. Riprova.")
    return False


def main() -> None:
    if not _check_password():
        return

    _init_session()

    with st.sidebar:
        st.markdown("## 📚 KDP Publishing House")
        st.divider()

        page = st.radio(
            "Navigazione",
            ["🏠 Dashboard", "📚 Book Builder", "🎨 Studio Mode", "📈 Marketing"],
            index=["🏠 Dashboard", "📚 Book Builder", "🎨 Studio Mode", "📈 Marketing"].index(
                st.session_state.nav_page
            ),
            key="nav_radio",
        )
        st.session_state.nav_page = page

        st.divider()

        proj = st.session_state.project
        niche_key = proj.get("niche")
        if niche_key:
            n = NICHES.get(niche_key, {})
            st.caption(f"**Progetto:** {n.get('emoji','')} {n.get('name', niche_key)}")
            st.caption(f"**Pagine:** {len(proj['pages'])} | **Illustrazioni:** {_count_illustrations()}/30")

        if st.button("🗑 Reset Progetto", use_container_width=True):
            st.session_state.project = {"niche": None, "pages": []}
            _save_project()
            st.session_state.nav_page = "🏠 Dashboard"
            st.rerun()

        st.divider()
        st.caption("The Daily Burnout Press\nv1.0 — 2026")

    # Route to page
    if page == "🏠 Dashboard":
        page_dashboard()
    elif page == "📚 Book Builder":
        page_book_builder()
    elif page == "🎨 Studio Mode":
        page_studio_mode()
    elif page == "📈 Marketing":
        page_marketing()


if __name__ == "__main__":
    main()
