#!/usr/bin/env python3
"""
KDP Publishing House — Streamlit Web App
Run: streamlit run app.py
"""

import io
import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image

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
from special_pages import make_qr_page, make_frontespizio, make_test_colors, make_black_page
from keyword_extractor import expand_keywords, MARKETS
from landing_page_generator import generate_landing_page

# ── Paths ─────────────────────────────────────────────────────────────────────
OUTPUT_PAGES   = Path("output/pages")
OUTPUT_SPECIAL = Path("output/special")
OUTPUT_FINAL   = Path("output/final")
PROJECT_FILE   = Path("output/current_project.json")
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
        "api_key":     os.environ.get("OPENAI_API_KEY", ""),
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
    key = st.session_state.api_key or os.environ.get("OPENAI_API_KEY", "")
    return key


def _generate_illustration(
    simbolo_angolo: str,
    simbolo_lato: str,
    soggetto_kawaii: str,
    phrase: str,
    threshold: int = BINARIZE_THR,
) -> Path:
    from openai import OpenAI

    client = OpenAI(api_key=_get_api_key() or None)
    prompt = MASTER_PROMPT_TEMPLATE.format(
        simbolo_angolo=simbolo_angolo,
        simbolo_lato=simbolo_lato,
        soggetto_kawaii=soggetto_kawaii,
    )
    raw   = generate_image(prompt, client)
    proc  = binarize(raw, threshold)
    proc  = enforce_white_text_zone(proc)
    kdp   = upscale_to_kdp(proc)
    final = inject_text(kdp, phrase)

    OUTPUT_PAGES.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_PAGES / f"page_{ts}_final.png"
    final.save(path, dpi=(OUTPUT_DPI, OUTPUT_DPI))
    return path


def _assemble_pdf_bytes() -> bytes:
    pages = st.session_state.project["pages"]
    images: list[Image.Image] = []
    for p in pages:
        try:
            img = Image.open(p["path"]).convert("RGB")
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
            st.error("API Key OpenAI mancante. Inseriscila nella sidebar.")

        # Subject selector
        if niche_key == "astrology":
            subjects = [
                {
                    "key": sign,
                    "label": ZODIAC_CONFIG[sign]["en_name"],
                    **{k: ZODIAC_CONFIG[sign][k] for k in ("simbolo_angolo", "simbolo_lato", "soggetto_kawaii")},
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
                        simbolo_angolo=subject_cfg["simbolo_angolo"],
                        simbolo_lato=subject_cfg["simbolo_lato"],
                        soggetto_kawaii=subject_cfg["soggetto_kawaii"],
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
                    thumb = _thumb(path)
                    if thumb:
                        st.image(thumb, caption=phrase[:50], width=200)
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
            rows = [pages[i:i+cols_per_row] for i in range(0, len(pages), cols_per_row)]

            for row_pages in rows:
                cols = st.columns(cols_per_row)
                for i, (col, page) in enumerate(zip(cols, row_pages)):
                    page_idx = pages.index(page)
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

    # ── Tab 4: Export PDF ─────────────────────────────────────────────────────
    with tab_export:
        st.subheader("Export PDF KDP")

        pages = proj["pages"]
        illus = _count_illustrations()

        col1, col2, col3 = st.columns(3)
        col1.metric("Pagine totali", len(pages))
        col2.metric("Illustrazioni", f"{illus}/30")
        col3.metric("Formato", "8.5\" × 11\"")

        if illus < 30:
            st.warning(f"Il libro ha {illus}/30 illustrazioni. Puoi esportare comunque come bozza.")

        if not pages:
            st.error("Nessuna pagina da esportare.")
        else:
            if st.button("📥 Genera PDF", type="primary"):
                with st.spinner("Assemblando PDF… (può richiedere qualche minuto)"):
                    pdf_bytes = _assemble_pdf_bytes()
                if pdf_bytes:
                    niche_name = NICHES.get(niche_key, {}).get("name", niche_key).replace(" ", "_")
                    filename   = f"kdp_{niche_name}_DRAFT.pdf"
                    st.download_button(
                        label=f"⬇️ Scarica {filename}",
                        data=pdf_bytes,
                        file_name=filename,
                        mime="application/pdf",
                        type="primary",
                    )
                    st.success(f"PDF generato: {len(pdf_bytes)/1e6:.1f} MB — {len(pages)} pagine")
                else:
                    st.error("Errore durante la generazione del PDF.")


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


def page_studio_mode() -> None:
    st.title("🎨 Studio Mode")
    st.caption("Controllo avanzato sulla generazione — per copertine e illustrazioni hero")

    if not _get_api_key():
        st.error("API Key OpenAI mancante. Inseriscila nella sidebar.")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("Parametri di Generazione")

        scene = st.text_area(
            "Descrizione Scena",
            placeholder="Es. exhausted office worker surrounded by paperwork and coffee cups, making a frustrated but funny face",
            height=100,
        )

        phrase = st.text_input(
            "Frase Satirica",
            placeholder='Es. "I survived another Monday"',
            max_chars=120,
        )

        text_style = st.selectbox(
            "Stile Integrazione Testo",
            list(TEXT_STYLES.keys()),
            help="Come la frase viene visivamente integrata nell'illustrazione",
        )

        fill_elements = st.text_input(
            "Elementi Riempitivi",
            placeholder="Es. coffee cups, papers, staplers, tiny plants",
            help="Oggetti extra da aggiungere nella scena, separati da virgola",
        )

        threshold = st.slider(
            "Threshold B/W",
            min_value=100, max_value=220, value=BINARIZE_THR, step=5,
            help="Valori più alti = più bianco. Default: 160",
        )

        dest = st.radio(
            "Destinazione output",
            ["📚 Aggiungi al Book Builder", "🖼 Salva in output/cover/"],
            horizontal=True,
        )

        generate_btn = st.button(
            "🎨 Genera",
            disabled=not scene or not _get_api_key(),
            type="primary",
            use_container_width=True,
        )

    with col_right:
        st.subheader("Preview e Quality Control")

        if generate_btn and scene:
            style_addition = TEXT_STYLES[text_style]
            fill_note = f" Include these fill elements scattered around: {fill_elements}." if fill_elements else ""

            prompt = MASTER_PROMPT_TEMPLATE.format(
                simbolo_angolo="decorative corner ornament with thematic elements",
                simbolo_lato="small decorative thematic symbol",
                soggetto_kawaii=f"{scene}, {style_addition}.{fill_note}",
            )

            with st.spinner("Generando… (~30 secondi)"):
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=_get_api_key() or None)
                    raw   = generate_image(prompt, client)
                    proc  = binarize(raw, threshold)
                    proc  = enforce_white_text_zone(proc)
                    kdp   = upscale_to_kdp(proc)

                    if phrase:
                        final = inject_text(kdp.copy(), phrase)
                    else:
                        final = kdp

                    # Quality metrics
                    import numpy as np
                    arr         = np.array(proc.convert("L"))
                    white_pct   = float((arr > 200).mean() * 100)
                    gray_pixels = int(((arr > 10) & (arr < 245)).sum())
                    kdp_ok      = gray_pixels < 1000

                    # Save
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    if "cover" in dest:
                        out_dir = Path("output/cover")
                    else:
                        out_dir = OUTPUT_PAGES
                    out_dir.mkdir(parents=True, exist_ok=True)
                    save_path = out_dir / f"studio_{ts}_final.png"
                    final.save(save_path, dpi=(OUTPUT_DPI, OUTPUT_DPI))

                    # Store in session for display
                    st.session_state["studio_last"] = {
                        "path": str(save_path),
                        "white_pct": white_pct,
                        "gray_pixels": gray_pixels,
                        "kdp_ok": kdp_ok,
                    }

                    if "Book Builder" in dest:
                        _add_page("illustration", save_path, {"phrase": phrase, "subject": "studio"})

                except Exception as e:
                    st.error(f"Errore: {e}")

        # Show last result
        last = st.session_state.get("studio_last")
        if last:
            thumb = _thumb(last["path"])
            if thumb:
                st.image(thumb, caption=Path(last["path"]).name, use_container_width=True)

            # Quality metrics
            st.markdown("**Quality Control**")
            c1, c2, c3 = st.columns(3)
            c1.metric("Pixel bianchi", f"{last['white_pct']:.1f}%")
            c2.metric("Pixel grigi residui", f"{last['gray_pixels']:,}")
            c3.metric("KDP Compliance", "✅ OK" if last["kdp_ok"] else "⚠️ Attenzione")

            if last["kdp_ok"]:
                st.success("✅ Immagine conforme agli standard KDP (100% B&N)")
            else:
                st.warning(f"⚠️ Trovati {last['gray_pixels']:,} pixel grigi. Prova ad aumentare il threshold.")

            with open(last["path"], "rb") as f:
                st.download_button(
                    "⬇️ Scarica PNG",
                    data=f.read(),
                    file_name=Path(last["path"]).name,
                    mime="image/png",
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

def main() -> None:
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
        st.markdown("**⚙️ Settings**")

        api_input = st.text_input(
            "OpenAI API Key",
            value=st.session_state.api_key,
            type="password",
            placeholder="sk-...",
            help="Oppure imposta la variabile OPENAI_API_KEY",
        )
        if api_input != st.session_state.api_key:
            st.session_state.api_key = api_input

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
