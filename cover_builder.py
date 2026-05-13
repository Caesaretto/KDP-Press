#!/usr/bin/env python3
"""
The Daily KDP Press — Cover Builder (KDP Wrap Composer)

Composes the full paperback wrap (back + spine + front) at 300 DPI per
KDP's official print specifications. Replaces the legacy interactive
`studio_mode.py`. Streamlit/app.py owns UX; this module is pure I/O-free
math + PIL composition.

Public API:
    compute_wrap_dimensions(page_count, paper, trim_w_in, trim_h_in, dpi, bleed_in) -> dict
    compose_wrap(front_illustration, dims, *, title, subtitle, publisher,
                 blurb, isbn="", spine_color_bg=(255,255,255),
                 include_barcode_area=True) -> PIL.Image

KDP wrap math reference (verified against KDP's "Print specifications →
Cover calculator", https://kdp.amazon.com/cover-calculator):

    Paper thickness per page (inches):
        white_60lb  = 0.002252
        cream_55lb  = 0.0025
        color_60lb  = 0.002347

    spine_width_in = page_count * thickness_per_page
    wrap_width_in  = 2 * (trim_w + bleed) + spine_width_in
    wrap_height_in = trim_h + 2 * bleed
    bleed_in       = 0.125  (KDP standard for paperback wraps)
    barcode area   = 2.0" x 1.2" white box, 0.25"-0.5" margin from
                     trim edge bottom-right (KDP requirement, leave clear)
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# OUTPUT_BASE is overridable via env (Railway mounts persistent volume).
COVER_DIR = Path(os.environ.get("OUTPUT_BASE", "output")) / "cover"

# Re-use shared helpers from sibling modules — DO NOT duplicate
from special_pages import _load_font  # noqa: F401  (font fallback ladder)
from generate_page import binarize    # noqa: F401  (B/W threshold helper for callers)


# ── KDP paper thickness lookup (inches per page) ─────────────────────────────
# Source: KDP Print Cover Calculator, Paperback Manuscript Templates (2024).
PAPER_THICKNESS_IN = {
    "white_60lb": 0.002252,
    "cream_55lb": 0.0025,
    "color_60lb": 0.002347,
    # Aliases for convenience
    "white":      0.002252,
    "cream":      0.0025,
    "color":      0.002347,
}

# Barcode placeholder size required by KDP / Amazon (inches)
BARCODE_W_IN = 2.0
BARCODE_H_IN = 1.2
BARCODE_MARGIN_IN = 0.5   # from trim edge (safe for all retailers)

# Title band on the front cover, as fraction of trim height
TITLE_BAND_TOP_FRAC = 0.70
TITLE_BAND_BOTTOM_PAD_FRAC = 0.04

# Minimum spine width to attempt vertical text (px). At 300 DPI this is ~0.17".
# KDP requires >=100 pages for printable spine text in their guidelines, but we
# render it whenever it physically fits and let the publisher decide.
MIN_SPINE_TEXT_PX = 50


# ── Math ─────────────────────────────────────────────────────────────────────

def compute_wrap_dimensions(
    page_count: int,
    paper: str = "white_60lb",
    trim_w_in: float = 8.5,
    trim_h_in: float = 11.0,
    dpi: int = 300,
    bleed_in: float = 0.125,
) -> dict:
    """Return pixel coords for the full KDP wrap.

    Layout (left-to-right): [back][spine][front], all at 300 DPI by default.
    """
    if paper not in PAPER_THICKNESS_IN:
        raise ValueError(
            f"Unknown paper '{paper}'. Valid: {sorted(PAPER_THICKNESS_IN)}"
        )
    if page_count < 24:
        raise ValueError("KDP requires a minimum of 24 interior pages.")

    thickness = PAPER_THICKNESS_IN[paper]
    spine_w_in = page_count * thickness
    wrap_w_in  = 2.0 * (trim_w_in + bleed_in) + spine_w_in
    wrap_h_in  = trim_h_in + 2.0 * bleed_in

    def px(v: float) -> int:
        return int(round(v * dpi))

    trim_w_px  = px(trim_w_in)
    trim_h_px  = px(trim_h_in)
    bleed_px   = px(bleed_in)
    spine_w_px = px(spine_w_in)
    wrap_w_px  = px(wrap_w_in)
    wrap_h_px  = px(wrap_h_in)

    # Panel x-origins (px). Back panel includes the LEFT bleed.
    back_x  = 0
    spine_x = bleed_px + trim_w_px            # right edge of back trim
    front_x = spine_x + spine_w_px            # left edge of front trim

    return {
        "wrap_w_px":  wrap_w_px,
        "wrap_h_px":  wrap_h_px,
        "spine_w_px": spine_w_px,
        "front_x":    front_x,
        "back_x":     back_x,
        "spine_x":    spine_x,
        "trim_w_px":  trim_w_px,
        "trim_h_px":  trim_h_px,
        "bleed_px":   bleed_px,
        "dpi":        dpi,
        "paper":      paper,
        "page_count": page_count,
        "spine_w_in": spine_w_in,
        "wrap_w_in":  wrap_w_in,
        "wrap_h_in":  wrap_h_in,
    }


# ── Text helpers ─────────────────────────────────────────────────────────────

def _wrap_text(text: str, font: "ImageFont.ImageFont", max_w: int,
               draw: ImageDraw.ImageDraw, max_lines: int = 12) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if (bbox[2] - bbox[0]) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        # ellipsize last line
        last = lines[-1]
        while last and (draw.textbbox((0, 0), last + "…", font=font)[2] > max_w):
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


def _centered_in(draw: ImageDraw.ImageDraw, x0: int, y: int, x1: int,
                 text: str, font: "ImageFont.ImageFont",
                 fill: tuple = (0, 0, 0)) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = x0 + ((x1 - x0) - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)


def _font_size(font: "ImageFont.ImageFont") -> int:
    """ImageFont.FreeTypeFont exposes .size; the bitmap fallback doesn't.
    Provide a sane default for the fallback."""
    return getattr(font, "size", 24)


# ── Composition ──────────────────────────────────────────────────────────────

def _paste_front(canvas: Image.Image, front_illustration: Image.Image,
                 dims: dict) -> None:
    """Resize illustration to fill front panel + outer bleed and paste."""
    target_w = dims["trim_w_px"] + dims["bleed_px"]   # right bleed
    target_h = dims["wrap_h_px"]                       # full wrap height
    scaled = front_illustration.resize((target_w, target_h), Image.BICUBIC)
    canvas.paste(scaled, (dims["front_x"], 0))


def _draw_title_band(canvas: Image.Image, dims: dict, title: str,
                     subtitle: str) -> None:
    draw = ImageDraw.Draw(canvas)
    fx0 = dims["front_x"]
    fx1 = fx0 + dims["trim_w_px"]
    band_top = dims["bleed_px"] + int(dims["trim_h_px"] * TITLE_BAND_TOP_FRAC)
    band_bot = dims["bleed_px"] + dims["trim_h_px"] - int(
        dims["trim_h_px"] * TITLE_BAND_BOTTOM_PAD_FRAC
    )
    inset = int(dims["trim_w_px"] * 0.06)
    # White band — flat white is fine for B/W KDP covers
    draw.rectangle(
        [(fx0 + inset, band_top), (fx1 - inset, band_bot)],
        fill=(255, 255, 255), outline=(0, 0, 0), width=4,
    )
    title_size = int(dims["trim_h_px"] * 0.060)
    sub_size   = int(dims["trim_h_px"] * 0.026)
    title_font = _load_font(title_size)
    sub_font   = _load_font(sub_size)

    # Title (one line, fitted)
    while _font_size(title_font) > 40:
        bbox = draw.textbbox((0, 0), title, font=title_font)
        if (bbox[2] - bbox[0]) <= (fx1 - fx0 - 2 * inset - 40):
            break
        title_size -= 6
        title_font = _load_font(title_size)

    pad_top = int((band_bot - band_top) * 0.10)
    _centered_in(draw, fx0 + inset, band_top + pad_top, fx1 - inset,
                 title, title_font)

    sub_lines = _wrap_text(subtitle, sub_font,
                           fx1 - fx0 - 2 * inset - 40, draw, max_lines=3)
    sy = band_top + pad_top + int(_font_size(title_font) * 1.25)
    for line in sub_lines:
        _centered_in(draw, fx0 + inset, sy, fx1 - inset, line, sub_font,
                     fill=(40, 40, 40))
        sy += int(_font_size(sub_font) * 1.2)


def _draw_spine(canvas: Image.Image, dims: dict, title: str, publisher: str,
                bg: tuple) -> None:
    if dims["spine_w_px"] < MIN_SPINE_TEXT_PX:
        # Spine too narrow — leave the panel blank background
        spine = Image.new("RGB",
                          (dims["spine_w_px"], dims["wrap_h_px"]),
                          bg)
        canvas.paste(spine, (dims["spine_x"], 0))
        return
    spine = Image.new("RGB",
                      (dims["spine_w_px"], dims["wrap_h_px"]),
                      bg)
    sdraw = ImageDraw.Draw(spine)
    sdraw.rectangle([(0, 0), (spine.size[0] - 1, spine.size[1] - 1)],
                    outline=(0, 0, 0), width=2)
    canvas.paste(spine, (dims["spine_x"], 0))

    # Render rotated title on its own canvas
    max_text_w = dims["wrap_h_px"] - 2 * dims["bleed_px"] - 200
    font_size = max(28, int(dims["spine_w_px"] * 0.55))
    font = _load_font(font_size)
    tmp = Image.new("RGB", (max_text_w, font_size + 40), bg)
    tdraw = ImageDraw.Draw(tmp)
    # shrink to fit
    while _font_size(font) > 24:
        bb = tdraw.textbbox((0, 0), title, font=font)
        if (bb[2] - bb[0]) <= max_text_w - 20:
            break
        font_size -= 4
        font = _load_font(font_size)
    bb = tdraw.textbbox((0, 0), title, font=font)
    tdraw.text(((max_text_w - (bb[2] - bb[0])) // 2,
                (tmp.height - (bb[3] - bb[1])) // 2 - bb[1]),
               title, font=font, fill=(0, 0, 0))
    rotated = tmp.rotate(-90, expand=True)
    rx = dims["spine_x"] + (dims["spine_w_px"] - rotated.width) // 2
    ry = (dims["wrap_h_px"] - rotated.height) // 2
    canvas.paste(rotated, (rx, ry))

    # Publisher (small, near bottom of spine)
    pub_size = max(18, int(dims["spine_w_px"] * 0.30))
    pub_font = _load_font(pub_size)
    ptmp_w = max_text_w
    ptmp = Image.new("RGB", (ptmp_w, pub_size + 20), bg)
    pdraw = ImageDraw.Draw(ptmp)
    bb = pdraw.textbbox((0, 0), publisher, font=pub_font)
    if (bb[2] - bb[0]) > ptmp_w - 10:
        pub_size = max(14, pub_size - 6)
        pub_font = _load_font(pub_size)
        bb = pdraw.textbbox((0, 0), publisher, font=pub_font)
    pdraw.text(((ptmp_w - (bb[2] - bb[0])) // 2, 4),
               publisher, font=pub_font, fill=(80, 80, 80))
    prot = ptmp.rotate(-90, expand=True)
    px = dims["spine_x"] + (dims["spine_w_px"] - prot.width) // 2
    py = dims["wrap_h_px"] - prot.height - dims["bleed_px"] - 80
    canvas.paste(prot, (px, py))


def _draw_back(canvas: Image.Image, dims: dict, blurb: str, isbn: str,
               include_barcode_area: bool) -> None:
    # Back panel background — solid white block over any front-bleed bleed-thru
    bx0 = dims["bleed_px"]
    bx1 = bx0 + dims["trim_w_px"]
    by0 = dims["bleed_px"]
    by1 = by0 + dims["trim_h_px"]
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([(0, 0), (dims["spine_x"], dims["wrap_h_px"])],
                   fill=(255, 255, 255))

    margin = int(dims["dpi"] * 0.5)        # 0.5" safe margin
    blurb_size = int(dims["trim_h_px"] * 0.022)
    blurb_font = _load_font(blurb_size)
    text_w = dims["trim_w_px"] - 2 * margin
    lines = _wrap_text(blurb, blurb_font, text_w, draw, max_lines=12)
    ty = by0 + margin
    for line in lines:
        draw.text((bx0 + margin, ty), line, font=blurb_font, fill=(0, 0, 0))
        ty += int(_font_size(blurb_font) * 1.35)

    if include_barcode_area:
        bw = int(BARCODE_W_IN * dims["dpi"])
        bh = int(BARCODE_H_IN * dims["dpi"])
        bm = int(BARCODE_MARGIN_IN * dims["dpi"])
        x0 = bx1 - bm - bw
        y0 = by1 - bm - bh
        draw.rectangle([(x0, y0), (x0 + bw, y0 + bh)],
                       fill=(255, 255, 255), outline=(0, 0, 0), width=3)
        bc_size = int(dims["dpi"] * 0.10)
        bc_font = _load_font(bc_size)
        small_font = _load_font(int(dims["dpi"] * 0.04))
        _centered_in(draw, x0, y0 + bh // 2 - bc_size,
                     x0 + bw, "BARCODE", bc_font, fill=(120, 120, 120))
        _centered_in(draw, x0, y0 + bh // 2 + 10,
                     x0 + bw, "(KDP autofills)", small_font,
                     fill=(150, 150, 150))

    if isbn:
        isbn_size = int(dims["dpi"] * 0.06)
        isbn_font = _load_font(isbn_size)
        draw.text((bx0 + margin, by1 - margin - isbn_size),
                  f"ISBN {isbn}", font=isbn_font, fill=(0, 0, 0))


def compose_wrap(
    front_illustration: Image.Image,
    dims: dict,
    *,
    title: str,
    subtitle: str,
    publisher: str,
    blurb: str,
    isbn: str = "",
    spine_color_bg: tuple = (255, 255, 255),
    include_barcode_area: bool = True,
) -> Image.Image:
    """Compose the full KDP wrap. `front_illustration` is the AI-generated
    B/W cover art (any size; will be resized). Returns a 300 DPI RGB image."""
    canvas = Image.new("RGB", (dims["wrap_w_px"], dims["wrap_h_px"]),
                       (255, 255, 255))
    _paste_front(canvas, front_illustration.convert("RGB"), dims)
    _draw_title_band(canvas, dims, title, subtitle)
    _draw_back(canvas, dims, blurb, isbn, include_barcode_area)
    _draw_spine(canvas, dims, title, publisher, spine_color_bg)
    return canvas


# ── Self-test ────────────────────────────────────────────────────────────────

def _placeholder_front(w: int = 1024, h: int = 1536) -> Image.Image:
    """Grayscale gradient — stand-in for an AI illustration."""
    img = Image.new("L", (w, h))
    pixels = img.load()
    for y in range(h):
        v = int(255 * (1 - y / h))
        for x in range(w):
            pixels[x, y] = max(0, min(255, v + ((x * 31) % 40) - 20))
    return img.convert("RGB")


def _selftest() -> None:
    out = COVER_DIR
    out.mkdir(parents=True, exist_ok=True)
    dims = compute_wrap_dimensions(page_count=65, paper="white_60lb")
    print("WRAP DIMS:")
    for k, v in dims.items():
        print(f"  {k:>12} = {v}")
    front = _placeholder_front()
    wrap = compose_wrap(
        front, dims,
        title="Zodiaco Esaurito",
        subtitle="Il libro da colorare per chi ha già abbastanza da gestire con le stelle",
        publisher="The Daily Burnout Press",
        blurb=("Dodici segni zodiacali, dodici crisi esistenziali, sessanta pagine "
               "di linee nere su sfondo bianco per riempire il vuoto cosmico con "
               "matite colorate. Pensato per chi ha letto l'oroscopo stamattina e "
               "ha capito che oggi è meglio non uscire. Ironico, kawaii, "
               "terapeutico (forse). Un regalo perfetto per chi sta ancora "
               "elaborando il transito di Saturno."),
        isbn="979-12-345-6789-0",
    )
    path = out / "test_wrap.png"
    wrap.save(path, dpi=(dims["dpi"], dims["dpi"]))
    print(f"\n  Wrote {path}  ({wrap.size[0]}x{wrap.size[1]} px)")


# ── Streamlit UI (called from app.py page_studio_mode → tab_cover) ───────────

COVER_PROMPT_DEFAULT = (
    "Black and white kawaii coloring book COVER illustration. "
    "Pure black outlines on pure white background. Bold uniform linework. "
    "Dense decorative composition, ornate border, kawaii style. "
    "NO text, letters, or numbers anywhere. NO gray, NO shading, NO gradients."
)


def render_cover_ui(get_api_key_fn, check_quota_fn,
                    generate_with_refund_fn, run_pipeline_fn) -> None:
    """Streamlit UI panel for full-wrap cover generation.

    Caller (app.py) supplies four functions to keep this module decoupled
    from app-level globals (api key resolver, quota guard, generator with
    refund-on-failure, post-processing pipeline).
    """
    import streamlit as st
    from datetime import datetime

    st.caption("Compone la wrap KDP completa (back + spine + front) con math verificata.")

    c1, c2, c3 = st.columns(3)
    page_count = c1.number_input("Pagine interne", min_value=24, max_value=828, value=65, step=1)
    paper      = c2.selectbox("Carta", ["white_60lb", "cream_55lb", "color_60lb"], index=0)
    trim       = c3.selectbox("Trim", ["8.5x11", "6x9", "8.5x8.5"], index=0)
    trim_w, trim_h = (8.5, 11.0) if trim == "8.5x11" else \
                     (6.0, 9.0)  if trim == "6x9"     else (8.5, 8.5)

    try:
        dims = compute_wrap_dimensions(int(page_count), paper=paper,
                                       trim_w_in=trim_w, trim_h_in=trim_h)
    except ValueError as e:
        st.error(str(e))
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Wrap W", f"{dims['wrap_w_px']} px")
    m2.metric("Wrap H", f"{dims['wrap_h_px']} px")
    m3.metric("Spine", f"{dims['spine_w_in']:.3f}\"")
    m4.metric("Spine px", f"{dims['spine_w_px']}")

    st.markdown("##### Metadati copertina")
    title    = st.text_input("Titolo",    value="Zodiaco Esaurito",       key="cb_title")
    subtitle = st.text_input("Sottotitolo", value="Il libro da colorare per chi ha già abbastanza", key="cb_sub")
    publisher = st.text_input("Editore",  value="The Daily Burnout Press", key="cb_pub")
    blurb    = st.text_area("Blurb retro", height=140, key="cb_blurb",
                            value="Dodici segni zodiacali, dodici crisi esistenziali, "
                                  "sessanta pagine di linee nere su sfondo bianco. "
                                  "Ironico, kawaii, terapeutico (forse).")
    isbn     = st.text_input("ISBN (opzionale)", value="", key="cb_isbn")
    barcode  = st.checkbox("Includi area barcode (KDP la riempie)", value=True, key="cb_bc")

    st.markdown("##### Generazione front (AI)")
    use_existing = st.checkbox("Usa illustrazione esistente",
                               value=False, key="cb_existing")
    front_path: Path | None = None
    front_prompt = ""
    if use_existing:
        existing = sorted(COVER_DIR.glob("*.png"))
        if not existing:
            st.warning("Nessuna PNG salvata. Genera con la tab Advanced o disattiva il toggle.")
        else:
            sel = st.selectbox("File", [p.name for p in existing], key="cb_existing_sel")
            front_path = COVER_DIR / sel
    else:
        front_prompt = st.text_area("Prompt front", height=180,
                                    value=COVER_PROMPT_DEFAULT, key="cb_prompt")

    do_compose = st.button("📕 Componi wrap", type="primary", key="cb_compose",
                           disabled=not get_api_key_fn() and not use_existing)
    if not do_compose:
        return

    try:
        if use_existing and front_path is not None:
            front_img = Image.open(front_path).convert("RGB")
        else:
            with st.spinner("Generando illustrazione front…"):
                raws = generate_with_refund_fn(
                    front_prompt, model="gpt-image-1", size="1024x1536",
                    quality="high", n=1,
                )
            # Run the pipeline at the front-panel size (back+bleed) for fidelity
            target_w = dims["trim_w_px"] + dims["bleed_px"]
            target_h = dims["wrap_h_px"]
            front_img, _ = run_pipeline_fn(
                raws[0], threshold=160, output_mode="B&W puro",
                pipeline_order="upscale_then_binarize", do_white_zone=False,
                phrase="", do_inject=False, use_zone_detector=False,
                out_w=target_w, out_h=target_h,
            )

        with st.spinner("Componendo wrap…"):
            wrap = compose_wrap(
                front_img, dims,
                title=title, subtitle=subtitle, publisher=publisher,
                blurb=blurb, isbn=isbn, include_barcode_area=barcode,
            )

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = COVER_DIR / f"wrap_{ts}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        wrap.save(out, dpi=(dims["dpi"], dims["dpi"]))

        st.success(f"Wrap salvato: {out}  ({wrap.size[0]}×{wrap.size[1]} px)")
        st.image(str(out), use_container_width=True)
        with open(out, "rb") as f:
            st.download_button("⬇️ Scarica wrap PNG", f.read(),
                               file_name=out.name, mime="image/png")
    except Exception as e:
        st.error(f"Errore: {e}")


if __name__ == "__main__":
    _selftest()
