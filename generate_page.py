#!/usr/bin/env python3
"""
The Daily KDP Press — Coloring Page Generator
Genera pagine B&N kawaii per coloring book KDP da segno zodiacale + frase ironica.

Usage:
    python generate_page.py leone "Il Leone porta la corona ma non sa fare nulla" it
    python generate_page.py pisces "Pisces cried today. And yesterday." en

    # Test post-processing su immagine esistente (senza chiamare l'API):
    python generate_page.py leone "frase test" it --skip-generate output/leone_raw.png

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

# ── KDP: 8.5" × 11" @ 300 DPI ────────────────────────────────────────────────
KDP_W, KDP_H   = 2550, 3300
TEXT_RATIO      = 0.30    # bottom fraction of image reserved for text
BORDER_RATIO    = 0.08    # decorative border width as fraction of image width
BINARIZE_THR    = 160
OUTPUT_DPI      = 300

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
# MASTER PROMPT TEMPLATE
# Parametri: {segno}, {soggetto_kawaii}, {elementi_tematici}, {simbolo_bordo}
# ══════════════════════════════════════════════════════════════════════════════

MASTER_PROMPT_TEMPLATE = """\
RENDERING STYLE — apply to the entire image without exception:
Black ink outlines on pure white paper. The background and all empty areas are \
bright white (paper white). Black is used only for outline strokes. \
No gray fills, no shading, no gradients, no shadows anywhere. \
This must look exactly like a coloring book page ready to be colored by a child — \
flat white areas bounded by clean black outlines, nothing else.

Black and white kawaii coloring book page for zodiac sign {segno}.

PAGE LAYOUT — replicate this structure exactly:
The full image is enclosed by a single ornate DECORATIVE BORDER that runs along \
all four edges of the image (top, bottom, left, right), like a tarot card picture frame. \
Inside the border, the content area is divided into two zones stacked vertically:
  — TOP 70%: kawaii illustration (see below)
  — BOTTOM 30%: blank white rectangle for text (see below)

SECTION 1 — DECORATIVE BORDER (all four sides, entire image perimeter):
  • Structure: double rectangular outline — a thick outer line and a thinner inner line, \
with a clear white gap between them on all four sides.
  • Corners: at each of the four corners, inside the gap, place a large {simbolo_bordo} \
ornament — prominent, detailed, completely filling the corner space.
  • Sides: between the two frame lines, the same {simbolo_bordo} motif repeats at \
regular intervals along ALL four sides (top, bottom, left, right), connected by a \
continuous thin ornamental vine or rope line that runs the full length of each side.
  • Border band width: approximately 8% of the total image width on each side.
  • Style: rich and decorative, like an ornate kawaii picture frame in a children's \
illustration book. Not minimalist. Not a simple single line. Dense with detail.

SECTION 2 — ILLUSTRATION ZONE (top 70% of interior, inside the border):
  • Main subject: {soggetto_kawaii}.
  • The subject is centered, drawn large, with thick clean outlines, \
big round sparkly eyes, rosy dot cheeks, kawaii proportions.
  • Background: almost empty white. Scatter only 3–4 tiny isolated elements \
({elementi_tematici}) with plenty of clean white space around them. \
No dense patterns, no background fills.

SECTION 3 — TEXT ZONE (bottom 30% of interior, inside the border):
  • Completely blank solid white rectangle. No drawings, no decorations, no lines.
  • A single thin horizontal rule separates this zone from the illustration above it.
  • The decorative border continues on the left, right, and bottom edges of this zone \
(it surrounds the entire page).

GLOBAL STYLE — critical, follow exactly:
  • This is a LINE DRAWING on white paper. The paper/background must be pure white \
(255,255,255) everywhere — do not fill any area with gray, black, or any shade.
  • Only the outline strokes themselves are black. Everything else is white.
  • No gray gradients, no drop shadows, no soft shading, no hatching, no crosshatching.
  • Think of it as: black ink pen on white paper, nothing else.
  • Bold uniform lineart. Coloring-book quality. High contrast.
  • DO NOT include any text, letters, numbers, or written symbols anywhere in the image.\
"""


# ══════════════════════════════════════════════════════════════════════════════
# ZODIAC DATA
# ══════════════════════════════════════════════════════════════════════════════

ZODIAC: dict[str, dict] = {
    "ariete": {
        "soggetto_kawaii":    "a chubby kawaii ram with big curly horns, rosy cheeks, and sparkly eyes, sitting proudly",
        "elementi_tematici":  "tiny flame, small star, sparkle cross",
        "simbolo_bordo":      "tiny ram head",
    },
    "toro": {
        "soggetto_kawaii":    "a cute kawaii bull with a round body, big soft eyes, and a small flower on its head",
        "elementi_tematici":  "tiny rose, small leaf, sparkle",
        "simbolo_bordo":      "tiny bull head",
    },
    "gemelli": {
        "soggetto_kawaii":    "two identical chubby kawaii star-children with faces, holding hands and smiling at each other",
        "elementi_tematici":  "tiny butterfly, small star, floating dot",
        "simbolo_bordo":      "tiny pair of stars side by side",
    },
    "cancro": {
        "soggetto_kawaii":    "a round kawaii crab with tiny claws raised, big sparkly eyes, and a happy expression",
        "elementi_tematici":  "tiny crescent moon, small bubble, sparkle",
        "simbolo_bordo":      "tiny crab silhouette",
    },
    "leone": {
        "soggetto_kawaii":    "a proud fluffy kawaii lion with a large round mane, sitting regally with its tail curled",
        "elementi_tematici":  "tiny sun ray, small crown, sparkle cross",
        "simbolo_bordo":      "tiny lion head with mane",
    },
    "vergine": {
        "soggetto_kawaii":    "a kawaii wheat sheaf bundle with a cute face, tied with a ribbon, surrounded by tiny daisies",
        "elementi_tematici":  "tiny flower, small leaf, floating dot",
        "simbolo_bordo":      "tiny daisy flower",
    },
    "bilancia": {
        "soggetto_kawaii":    "a pair of kawaii golden scales in perfect balance, each pan holding a tiny glowing star",
        "elementi_tematici":  "tiny feather, small star, sparkle",
        "simbolo_bordo":      "tiny scales symbol",
    },
    "scorpione": {
        "soggetto_kawaii":    "a chubby kawaii scorpion with a curled striped tail, big round eyes, and tiny claws",
        "elementi_tematici":  "tiny crescent moon, small star, sparkle cross",
        "simbolo_bordo":      "tiny scorpion silhouette",
    },
    "sagittario": {
        "soggetto_kawaii":    "a kawaii centaur foal — cute round horse body with a small chibi archer on top, holding a tiny bow",
        "elementi_tematici":  "tiny arrow, small star, sparkle",
        "simbolo_bordo":      "tiny arrow pointing right",
    },
    "capricorno": {
        "soggetto_kawaii":    "a kawaii sea-goat with small curved horns, a fish tail, and big round eyes, jumping happily",
        "elementi_tematici":  "tiny snowflake, small gem, sparkle cross",
        "simbolo_bordo":      "tiny sea-goat head",
    },
    "acquario": {
        "soggetto_kawaii":    "a kawaii round water jug with a cute face, pouring a swirling arc of sparkly water drops",
        "elementi_tematici":  "tiny water drop, small lightning bolt, bubble",
        "simbolo_bordo":      "tiny water wave",
    },
    "pesci": {
        "soggetto_kawaii":    "two chubby kawaii fish swimming nose-to-tail in a gentle circle, both smiling",
        "elementi_tematici":  "tiny bubble, small heart, sparkle cross",
        "simbolo_bordo":      "tiny fish",
    },
}

# English aliases pointing to Italian entries
_ALIASES = {
    "aries": "ariete", "taurus": "toro", "gemini": "gemelli", "cancer": "cancro",
    "leo": "leone", "virgo": "vergine", "libra": "bilancia", "scorpio": "scorpione",
    "sagittarius": "sagittario", "capricorn": "capricorno", "aquarius": "acquario",
    "pisces": "pesci",
}


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def build_prompt(sign: str) -> str:
    key  = _ALIASES.get(sign, sign)
    data = ZODIAC.get(key)
    if data is None:
        data = {
            "soggetto_kawaii":   f"a kawaii {sign} symbol with big round eyes and rosy cheeks",
            "elementi_tematici": "tiny star, small heart, sparkle",
            "simbolo_bordo":     f"tiny {sign} symbol",
        }
    return MASTER_PROMPT_TEMPLATE.format(segno=sign.capitalize(), **data)


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
        with urllib.request.urlopen(item.url) as r:
            img_bytes = r.read()
    else:
        raise RuntimeError("OpenAI response: no b64_json or url found.")
    return Image.open(BytesIO(img_bytes)).convert("RGB")


def binarize(img: Image.Image, threshold: int = BINARIZE_THR) -> Image.Image:
    gray = img.convert("L")
    return gray.point(lambda p: 255 if p > threshold else 0, "L").convert("RGB")


def enforce_white_text_zone(img: Image.Image) -> Image.Image:
    """Wipe the interior of the text zone to pure white, preserving border strip on sides/bottom."""
    w, h     = img.size
    margin   = int(w * BORDER_RATIO)   # estimated border width to leave intact
    zone_y   = int(h * (1 - TEXT_RATIO))
    draw     = ImageDraw.Draw(img)
    # Clear interior only: inset by margin on left, right, and bottom
    draw.rectangle([(margin, zone_y), (w - margin, h - margin)], fill=(255, 255, 255))
    return img


def upscale_to_kdp(img: Image.Image) -> Image.Image:
    if img.size == (KDP_W, KDP_H):
        return img
    return img.resize((KDP_W, KDP_H), Image.LANCZOS)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    print("  ⚠ No TrueType font found — falling back to PIL default", file=sys.stderr)
    return ImageFont.load_default()


def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str,
                   font: ImageFont.FreeTypeFont, max_px: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        candidate = f"{cur} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_px:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [text]


def inject_text(img: Image.Image, phrase: str) -> Image.Image:
    w, h        = img.size
    border_px   = int(w * BORDER_RATIO)
    # Text area: inside border on sides, inside border at bottom
    zone_top    = int(h * (1 - TEXT_RATIO))
    zone_bottom = h - border_px
    zone_h      = zone_bottom - zone_top
    # Horizontal padding: border width + breathing room
    h_padding   = border_px + int(w * 0.06)
    max_text_w  = w - 2 * h_padding
    target_h    = int(zone_h * 0.60)   # text fills 60% of available interior height

    draw = ImageDraw.Draw(img)

    best_font, best_lines, best_gap = None, [phrase], 0
    for fs in range(220, 18, -3):
        font     = _load_font(fs)
        lines    = _wrap_to_width(draw, phrase, font, max_text_w)
        line_gap = int(fs * 0.55)
        line_h   = draw.textbbox((0, 0), "Ay", font=font)[3]
        blk_h    = line_h * len(lines) + line_gap * (len(lines) - 1)
        max_lw   = max(draw.textbbox((0, 0), ln, font=font)[2] for ln in lines)
        if blk_h <= target_h and max_lw <= max_text_w:
            best_font, best_lines, best_gap = font, lines, line_gap
            break

    if best_font is None:
        best_font  = _load_font(20)
        best_lines = _wrap_to_width(draw, phrase, best_font, max_text_w)
        best_gap   = 6

    font     = best_font
    line_h   = draw.textbbox((0, 0), "Ay", font=font)[3]
    blk_h    = line_h * len(best_lines) + best_gap * (len(best_lines) - 1)
    y_start  = zone_top + (zone_h - blk_h) // 2   # centered in interior zone
    stroke   = max(4, int(line_h * 0.08))

    y = y_start
    for line in best_lines:
        lw = draw.textbbox((0, 0), line, font=font)[2]
        x  = (w - lw) // 2
        draw.text((x, y), line, font=font,
                  fill=(255, 255, 255), stroke_width=stroke, stroke_fill=(0, 0, 0))
        y += line_h + best_gap

    return img


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
    parser.add_argument("--out-dir",       default="output", metavar="DIR")
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

    # 1. Raw image
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

    # 2. Binarize + enforce white text zone
    print(f"[2/4] Binarizing (threshold={args.threshold})…")
    proc = binarize(raw_img, args.threshold)
    proc = enforce_white_text_zone(proc)

    # 3. Upscale to KDP
    print(f"[3/4] Upscaling to {KDP_W}×{KDP_H} px…")
    kdp = upscale_to_kdp(proc)

    # 4. Inject text
    print(f'[4/4] Injecting: "{args.phrase}"')
    final = inject_text(kdp, args.phrase)

    final_path = out_dir / f"{slug}_final.png"
    final.save(final_path, dpi=(OUTPUT_DPI, OUTPUT_DPI))

    print(f"\n✓  {final_path}")
    print(f"   {final.size[0]}×{final.size[1]} px | {OUTPUT_DPI} DPI | {final_path.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
