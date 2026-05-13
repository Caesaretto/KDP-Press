#!/usr/bin/env python3
"""
The Daily KDP Press — Coloring Page Generator
Genera pagine B&N kawaii per coloring book KDP da segno zodiacale + frase ironica.

Usage:
    python generate_page.py leone "Il Leone porta la corona ma non sa fare nulla" it
    python generate_page.py pisces "Pisces cried today. And yesterday." en

    # Test post-processing su immagine esistente (senza chiamare l'API):
    python generate_page.py leone "frase test" it --skip-generate output/leone_raw.png

    # Stampa il prompt senza generare:
    python generate_page.py pesci "test" it --print-prompt

Requirements:
    pip install openai pillow
    export OPENAI_API_KEY=sk-...
"""

import argparse
import base64
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

from zodiac_config import ZODIAC_CONFIG, _ALIASES

# ── KDP: 8.5" × 11" @ 300 DPI ────────────────────────────────────────────────
KDP_W, KDP_H    = 2550, 3300
TEXT_RATIO       = 0.30    # bottom fraction reserved for text zone
BORDER_RATIO     = 0.08    # decorative border width as fraction of image width
BINARIZE_THR     = 160
OUTPUT_DPI       = 300

# ── Font candidates — Fredoka One first for kawaii look ──────────────────────
_SCRIPT_DIR = Path(__file__).parent
FONT_CANDIDATES = [
    str(_SCRIPT_DIR / "fonts" / "FredokaOne-Regular.ttf"),
    "/usr/share/fonts/chromeos/monotype/comicbd.ttf",
    "/usr/share/fonts/chromeos/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/chromeos/croscore/Arimo-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


# ══════════════════════════════════════════════════════════════════════════════
# MASTER PROMPT TEMPLATE v2 — kawaii tarot-card editorial style
# Parameters: {soggetto_kawaii}, {glyph_unicode}, {thematic_prop}, {scatter_elements}
# Synthesis di 3 agenti specializzati (visual analysis + prompt engineering + arch).
# Riferimenti: refs/ref_01_aquarius.jpg, refs/ref_02_pisces.jpg
# ══════════════════════════════════════════════════════════════════════════════

MASTER_PROMPT_TEMPLATE = """\
A single page from a kawaii children's coloring book. The page background is \
pure white paper #FFFFFF EVERYWHERE — never dark, never inverted, never \
filled with black. On top of this white paper, thin uniform BLACK ink lines \
(#000000) draw the illustration as hollow outlines. Every enclosed shape is \
filled with pure white #FFFFFF, ready to be colored in by a child with crayons. \
Imagine the kind of clean printed coloring book page you'd find in a kids' \
activity book — white paper, black lines, nothing else.

NO black background. NO dark backgrounds. NO solid color fills. NO inverted \
images (white-on-black). NO grayscale, NO shading, NO gradients, NO hatching, \
NO stippling, NO textures.

═══ PAGE COMPOSITION (vertical 4:5 portrait, three horizontal regions inside the border) ═══
- UPPER REGION (about two thirds of the page): main kawaii illustration with \
generous breathing white space around it
- LOWER REGION (about one third of the page, clearly visible as an empty white \
rectangular band as tall as half the illustration region): completely empty \
pure-white area reserved for caption — NO illustrations, NO decorations, NO \
text inside this band, just clean empty white space
- COPYRIGHT line (just below the outer border, outside the decorative frame): \
tiny thin sans-serif "© 2026", centered, solid thin black

═══ DECORATIVE BORDER (double-frame ornate kawaii style, occupies the outer ~7% of each page side) ═══
- OUTER FRAME: thick crisp black rectangle around the ENTIRE page including \
above, below, and beside the empty white caption band. Corners slightly \
chamfered at 45 degrees.
- INNER FRAME: a second parallel thinner black rectangle drawn ~15 pixels \
inside the outer frame, same chamfered corners.
- FOUR CORNERS: each corner contains one large 5-pointed star + the \
astrological glyph {glyph_unicode} (medium size) + 2 or 3 satellite tiny stars \
arranged organically. This corner cluster crosses both inner and outer frame \
lines, visually breaking the rectangle.
- FOUR SIDES (top, bottom, left, right — ALL FOUR, especially BOTTOM): between \
corners, alternate medium 5-pointed stars (3 to 4 per long side) with the \
astrological glyph {glyph_unicode} repeated (1 to 2 per long side), distributed \
ASYMMETRICALLY (NOT on a strict grid). Elements bridge both frame lines.
- The decorative border on the BOTTOM side (below the empty white caption band) \
is EQUALLY ornate and complete as the top border. It must NOT be missing or \
simplified.

═══ MAIN ILLUSTRATION (upper region only, centered) ═══
- Subject: {soggetto_kawaii}
- Proportions: chibi kawaii — head-to-body ratio approximately 1 to 1 for \
humanoid characters, oversized cute features for animal characters
- Face details: large round black eyes with a single white circular highlight \
inside each eye, small curved smile, two tiny round blush cheeks
- Size: subject occupies about 55 to 65 percent of the illustration region \
width, centered horizontally, positioned slightly above the vertical center \
of the upper region, with generous white margin around it (never touching \
the border)
- ZODIAC MARKER ON-CHARACTER: draw the astrological glyph {glyph_unicode} \
directly onto the subject's body as a small decorative tattoo or marking \
(on the cheek, shoulder, forehead, or fin — depending on subject anatomy)
- THEMATIC CONTEXT PROP: include {thematic_prop} near or behind the subject \
as a small supporting element

═══ SCATTERED BACKGROUND ACCENTS (upper region only, in the white space around the subject) ═══
- Place 3 to 6 medium-sized thematic decorations: {scatter_elements}
- Each accent is medium-sized (roughly 5 to 10 percent of page width), NOT \
microscopic
- Distribute asymmetrically — never aligned, never on a grid, never touching \
each other or the subject or the border
- Each accent isolated, separated from neighbors by at least 200 pixels of \
pure white empty space

═══ STRICT RULES (must ALL hold simultaneously — these override anything else) ═══
- THE PAGE BACKGROUND IS PURE WHITE #FFFFFF EVERYWHERE. Never black, never \
dark, never inverted. The drawing is always thin BLACK lines on WHITE paper, \
NEVER the opposite.
- The decorative border closes completely on ALL FOUR sides; the bottom \
border below the empty caption band is fully drawn and ornate.
- The lower one-third caption band is a pure white #FFFFFF rectangle with NO \
illustrations, NO patterns, NO text, NO decorations of any kind inside it \
(but the border around it is fully drawn).
- NO letters, NO numbers, NO runes, NO words, NO captions, NO signatures, NO \
watermarks, NO ghost text anywhere in the image other than the tiny "© 2026" \
copyright line below the outer border.
- Only two colors exist in this image: pure black #000000 (the line art) and \
pure white #FFFFFF (everything else). No grays, no halftones, no shading, no \
gradients, no crosshatching, no stippling, no patterned fills.
- All linework has uniform thin stroke weight, like a printed children's \
coloring book.
- Subject occupies at most 65 percent of the illustration region (preserves \
white breathing room).\
"""


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def build_prompt(sign: str) -> str:
    key  = _ALIASES.get(sign, sign)
    data = ZODIAC_CONFIG.get(key)
    if data is None:
        data = {
            "glyph_unicode":    "★",
            "soggetto_kawaii":  f"one adorable kawaii {sign} character with big round eyes and rosy cheeks",
            "thematic_prop":    f"a small {sign}-themed prop",
            "scatter_elements": "small 5-pointed stars, tiny hearts, small swirls",
        }
    return MASTER_PROMPT_TEMPLATE.format(
        glyph_unicode=data.get("glyph_unicode", "★"),
        soggetto_kawaii=data["soggetto_kawaii"],
        thematic_prop=data.get("thematic_prop", "a small thematic prop"),
        scatter_elements=data.get(
            "scatter_elements",
            "small 5-pointed stars, tiny hearts, small swirls",
        ),
    )


def generate_image(prompt: str, client: OpenAI) -> Image.Image:
    print("  → Calling gpt-image-1…", flush=True)
    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1536",
        quality="high",
        n=1,
    )
    item = response.data[0]
    if hasattr(item, "b64_json") and item.b64_json:
        img_bytes = base64.b64decode(item.b64_json)
    elif hasattr(item, "url") and item.url:
        import urllib.request
        from urllib.parse import urlparse
        parsed = urlparse(item.url)
        if parsed.scheme != "https" or not parsed.hostname or not (
            parsed.hostname.endswith(".openai.com")
            or parsed.hostname.endswith(".oaiusercontent.com")
            or parsed.hostname.endswith(".azure.com")
        ):
            raise RuntimeError(f"Refusing to fetch image from unexpected host: {parsed.hostname}")
        with urllib.request.urlopen(item.url, timeout=30) as r:
            img_bytes = r.read()
    else:
        raise RuntimeError("OpenAI response: no b64_json or url found.")
    return Image.open(BytesIO(img_bytes)).convert("RGB")


def binarize(img: Image.Image, threshold: int = BINARIZE_THR) -> Image.Image:
    gray = img.convert("L")
    return gray.point(lambda p: 255 if p > threshold else 0, "L").convert("RGB")


def enforce_white_text_zone(img: Image.Image) -> Image.Image:
    """Wipe the INTERIOR of the lower text band to pure white WITHOUT touching
    the decorative border on top/bottom/sides of that band.

    Bug pre-fix: the previous version used a gutter of just BORDER_RATIO (8%)
    which clipped the inner ornamental line + lateral simboli of the tarot-card
    border. We now use 1.4x BORDER_RATIO as gutter so the decorative frame on
    every side of the text band survives.
    """
    w, h         = img.size
    border_outer = int(w * BORDER_RATIO)
    gutter       = int(w * BORDER_RATIO * 1.4)  # leave 40% extra so border art survives
    zone_y_top   = int(h * (1 - TEXT_RATIO)) + int(h * 0.02)  # 2% top pad → no clip
                                                              # of illustration tails
    zone_y_bot   = h - gutter
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [(gutter, zone_y_top), (w - gutter, zone_y_bot)],
        fill=(255, 255, 255),
    )
    return img


def upscale_to_kdp(img: Image.Image) -> Image.Image:
    if img.size == (KDP_W, KDP_H):
        return img
    # BICUBIC: sharper edges than LANCZOS for binary line art that will be
    # re-binarized post-upscale. Lower stroke-halo than NEAREST.
    return img.resize((KDP_W, KDP_H), Image.BICUBIC)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    print("  ⚠ No TrueType font found — falling back to PIL default", file=sys.stderr)
    return ImageFont.load_default()


def _stroke_for(font_size: int) -> int:
    """Stroke width per outline-text. ~6% del corpo del glifo, clamped per non
    saturare l'interno dei caratteri piccoli. Allineato alle reference visive
    (refs/ref_01_aquarius.jpg, refs/ref_02_pisces.jpg)."""
    proportional = round(font_size * 0.06)
    return max(3, min(proportional, font_size // 4))


def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str,
                   font: ImageFont.FreeTypeFont, max_px: int,
                   stroke_width: int = 0) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        candidate = f"{cur} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font, stroke_width=stroke_width)
        if bbox[2] <= max_px:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [text]


def outline_text(img: Image.Image, phrase: str) -> Image.Image:
    """Render the phrase as HOLLOW OUTLINE LETTERS (white fill, thick black
    stroke) in the lower text band, so the letters themselves are colorable.

    Replaces the legacy inject_text() which drew solid black text. The new
    behavior matches the editorial coloring-book references in refs/.

    All-caps uppercase rendering (refs are uppercase), centered, line-break
    by word-wrap. Auto-fits the largest font size that fits the band height
    while preserving padding from the decorative border.
    """
    w, h        = img.size
    phrase      = phrase.upper()  # references are all-caps
    border_px   = int(w * BORDER_RATIO)
    inner_pad   = int(w * 0.04)         # extra gutter past the decorative border
    zone_top    = int(h * (1 - TEXT_RATIO))
    zone_bottom = h - border_px - inner_pad
    zone_h      = zone_bottom - zone_top
    h_padding   = border_px + inner_pad + int(w * 0.04)
    max_text_w  = w - 2 * h_padding
    target_h    = int(zone_h * 0.78)    # use most of the band; outline letters
                                        # are visually heavy so we maximize

    draw = ImageDraw.Draw(img)

    best_font, best_lines, best_gap, best_stroke = None, [phrase], 0, 0
    for fs in range(280, 28, -4):
        font     = _load_font(fs)
        stroke   = _stroke_for(fs)
        lines    = _wrap_to_width(draw, phrase, font, max_text_w, stroke_width=stroke)
        line_gap = int(fs * 0.18)        # tight line-height ~1.15 like refs
        line_h   = draw.textbbox((0, 0), "Ay", font=font, stroke_width=stroke)[3]
        blk_h    = line_h * len(lines) + line_gap * (len(lines) - 1)
        max_lw   = max(
            draw.textbbox((0, 0), ln, font=font, stroke_width=stroke)[2]
            for ln in lines
        )
        if blk_h <= target_h and max_lw <= max_text_w:
            best_font, best_lines, best_gap, best_stroke = font, lines, line_gap, stroke
            break

    if best_font is None:
        best_font   = _load_font(28)
        best_stroke = _stroke_for(28)
        best_lines  = _wrap_to_width(draw, phrase, best_font, max_text_w,
                                     stroke_width=best_stroke)
        best_gap    = 6

    font   = best_font
    stroke = best_stroke
    line_h = draw.textbbox((0, 0), "Ay", font=font, stroke_width=stroke)[3]
    blk_h  = line_h * len(best_lines) + best_gap * (len(best_lines) - 1)
    y_start = zone_top + (zone_h - blk_h) // 2

    y = y_start
    for line in best_lines:
        lw = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)[2]
        x  = (w - lw) // 2
        # OUTLINE LETTERING: black contour + white interior → colorable
        draw.text(
            (x, y), line, font=font,
            fill=(255, 255, 255),
            stroke_width=stroke,
            stroke_fill=(0, 0, 0),
        )
        y += line_h + best_gap

    return img


# Backward-compat alias for callers still importing inject_text
inject_text = outline_text


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="The Daily KDP Press — Coloring Page Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("sign",     help="Zodiac sign (e.g. leone, pesci, leo, pisces)")
    parser.add_argument("phrase",   help="Ironic phrase to inject in the text zone")
    parser.add_argument("language", help="Language code (it / en / es / fr …)")
    parser.add_argument("--out-dir",       default="output/pages", metavar="DIR")
    parser.add_argument("--threshold",     type=int, default=BINARIZE_THR, metavar="N",
                        help=f"Binarization threshold 0–255 (default: {BINARIZE_THR})")
    parser.add_argument("--skip-generate", metavar="IMAGE_PATH",
                        help="Skip API — use existing raw image (for testing post-processing)")
    parser.add_argument("--print-prompt",  action="store_true",
                        help="Print the generated prompt and exit without calling the API")
    args = parser.parse_args()

    sign    = args.sign.lower()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prompt = build_prompt(sign)

    if args.print_prompt:
        print(prompt)
        return

    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = f"{sign}_{ts}"

    if args.skip_generate:
        print(f"[1/4] Loading: {args.skip_generate}")
        raw_img = Image.open(args.skip_generate).convert("RGB")
    else:
        print(f"[1/4] Generating '{sign}' ({args.language}) — {len(prompt)} char prompt…")
        client  = OpenAI()
        raw_img = generate_image(prompt, client)
        raw_path = out_dir / f"{slug}_raw.png"
        raw_img.save(raw_path)
        print(f"      → {raw_path}")

    print(f"[2/4] Upscaling to {KDP_W}×{KDP_H} px…")
    kdp = upscale_to_kdp(raw_img)

    print(f"[3/4] Binarizing (threshold={args.threshold})…")
    proc = binarize(kdp, args.threshold)
    proc = enforce_white_text_zone(proc)

    print(f'[4/4] Injecting: "{args.phrase}"')
    final = inject_text(proc, args.phrase)

    final_path = out_dir / f"{slug}_final.png"
    final.save(final_path, dpi=(OUTPUT_DPI, OUTPUT_DPI))

    print(f"\n✓  {final_path}")
    print(f"   {final.size[0]}×{final.size[1]} px | {OUTPUT_DPI} DPI | {final_path.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
