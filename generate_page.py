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
# MASTER PROMPT TEMPLATE
# Parameters: {simbolo_angolo}, {simbolo_lato}, {soggetto_kawaii}
# ══════════════════════════════════════════════════════════════════════════════

MASTER_PROMPT_TEMPLATE = """\
Black and white kawaii coloring book illustration page. Pure black outlines on \
pure white background. Zero gray shading, zero gradients, zero textures. \
Bold uniform linework throughout.

PAGE LAYOUT (critical - follow exactly):
The page is divided into two sections, both INSIDE the decorative border:
- TOP 70%: kawaii illustration area with clean white background
- BOTTOM 30%: completely empty white rectangle, no illustrations, no text, \
no decorations whatsoever

DECORATIVE BORDER (critical - must surround the ENTIRE page including the \
bottom white area):
- Outer thick black line forming a complete rectangle around the full page
- Inner thin black line parallel to outer line, with decorative space between them
- Four corners: large {simbolo_angolo} filling each corner space
- All four sides (top, bottom, left, right): {simbolo_lato} repeated at regular \
intervals along the entire side, connected by a thin ornamental line
- Border width: approximately 8% of page width on each side
- Style: kawaii tarot card border, ornate but clean

MAIN ILLUSTRATION (inside the top 70% of the border):
- Subject: {soggetto_kawaii}
- Style: chibi kawaii, big cute round eyes, simple happy expression, rounded shapes
- Size: fills approximately 80% of the illustration area
- Background: pure white with maximum 4 small decorative elements scattered \
(4-pointed stars, tiny hearts, small circles/bubbles)
- NO patterns, NO dense backgrounds, NO competing elements

ABSOLUTE RULES:
- NO text anywhere in the image (not even single letters or symbols that look like text)
- NO gray pixels anywhere
- NO shading or gradients
- The bottom 30% must be completely empty white space
- The decorative border must be complete on ALL FOUR sides including around \
the bottom white area\
"""


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def build_prompt(sign: str) -> str:
    key  = _ALIASES.get(sign, sign)
    data = ZODIAC_CONFIG.get(key)
    if data is None:
        data = {
            "simbolo_angolo":  f"{sign} stylized decorative element",
            "simbolo_lato":    f"small cute {sign} symbol",
            "soggetto_kawaii": f"one adorable kawaii {sign} symbol with big round eyes and rosy cheeks",
        }
    return MASTER_PROMPT_TEMPLATE.format(
        simbolo_angolo=data["simbolo_angolo"],
        simbolo_lato=data["simbolo_lato"],
        soggetto_kawaii=data["soggetto_kawaii"],
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
    """Wipe the interior of the text zone to pure white, preserving the border strip."""
    w, h    = img.size
    margin  = int(w * BORDER_RATIO)
    zone_y  = int(h * (1 - TEXT_RATIO))
    draw    = ImageDraw.Draw(img)
    draw.rectangle([(margin, zone_y), (w - margin, h - margin)], fill=(255, 255, 255))
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
    zone_top    = int(h * (1 - TEXT_RATIO))
    zone_bottom = h - border_px
    zone_h      = zone_bottom - zone_top
    h_padding   = border_px + int(w * 0.06)
    max_text_w  = w - 2 * h_padding
    target_h    = int(zone_h * 0.60)

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

    font   = best_font
    line_h = draw.textbbox((0, 0), "Ay", font=font)[3]
    blk_h  = line_h * len(best_lines) + best_gap * (len(best_lines) - 1)
    y_start = zone_top + (zone_h - blk_h) // 2

    y = y_start
    for line in best_lines:
        lw = draw.textbbox((0, 0), line, font=font)[2]
        x  = (w - lw) // 2
        draw.text((x, y), line, font=font, fill=(0, 0, 0))
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
