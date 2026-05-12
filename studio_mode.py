#!/usr/bin/env python3
"""
DEPRECATED — use cover_builder.py and the in-app Studio Mode (Streamlit) instead.

This module computed an INCORRECT wrap size (3331×2551) for KDP paperback, did
not produce a valid spine, lacked the back-cover barcode area, and had no SSRF
protection on remote image fetches. It is kept only for historical reference.

The current pipeline:
  - cover composition  → cover_builder.py
  - interactive UI     → app.py page_studio_mode (Streamlit "Studio Mode" tab)

Running this module prints a deprecation warning and exits.
"""

import argparse
import base64
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

# ── Cover dimensions @ 300 DPI ────────────────────────────────────────────────
COVER_W, COVER_H = 3331, 2551
OUTPUT_DPI       = 300
BINARIZE_THR     = 170     # slightly softer than interior pages

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

BOOK_TITLE     = "Zodiaco Esaurito"
BOOK_SUBTITLE  = "Il libro da colorare per chi ha già abbastanza da gestire con le stelle"
BOOK_PUBLISHER = "The Daily Burnout Press"
BOOK_AUTHOR    = ""  # set if needed

DEFAULT_SCENE = (
    "all twelve kawaii zodiac animals arranged in a circle around a central sun, "
    "each animal adorable chibi style with big round eyes, "
    "surrounded by tiny stars hearts and celestial symbols, "
    "clean decorative border around the full illustration"
)

COVER_PROMPT_TEMPLATE = """\
Black and white kawaii coloring book COVER illustration. Pure black outlines on \
pure white background. Zero gray shading, zero gradients, zero textures. \
Bold uniform linework. Professional book cover composition.

COVER ILLUSTRATION:
- {scene}
- Style: chibi kawaii, bold clean linework, high contrast black and white
- The illustration should fill the entire image area as a dense, beautiful composition
- Include a decorative ornate border around the edges (double line with corner ornaments)
- Background: pure white with decorative star/celestial scatter elements
- Mood: playful, whimsical, ironic — a gift book cover

ABSOLUTE RULES:
- NO text, letters, numbers, or written symbols anywhere
- NO gray pixels — pure black and white only
- NO shading or gradients
- Dense but not cluttered — clear focal point in center\
"""


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def generate_cover_image(prompt: str, client: OpenAI) -> Image.Image:
    print("  → Calling gpt-image-1 (cover)…", flush=True)
    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1536x1024",   # landscape for cover wrap
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


def upscale_to_cover(img: Image.Image) -> Image.Image:
    if img.size == (COVER_W, COVER_H):
        return img
    return img.resize((COVER_W, COVER_H), Image.LANCZOS)


def _centered_text(draw: ImageDraw.ImageDraw, y: int, text: str,
                   font: ImageFont.FreeTypeFont, fill: tuple = (0, 0, 0),
                   width: int = COVER_W) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (width - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, font=font, fill=fill)


def inject_cover_text(img: Image.Image) -> Image.Image:
    """Overlay title, subtitle, and publisher text on the cover illustration."""
    draw = ImageDraw.Draw(img)

    title_font  = _load_font(180)
    sub_font    = _load_font(70)
    pub_font    = _load_font(55)

    # Semi-transparent white band for title legibility (drawn as white rectangle)
    band_top    = int(COVER_H * 0.72)
    band_bottom = COVER_H - 60
    draw.rectangle([(60, band_top), (COVER_W - 60, band_bottom)], fill=(255, 255, 255))

    _centered_text(draw, band_top + 20, BOOK_TITLE,    title_font)
    _centered_text(draw, band_top + 220, BOOK_SUBTITLE, sub_font)
    _centered_text(draw, band_bottom - 80, BOOK_PUBLISHER, pub_font, fill=(80, 80, 80))

    return img


def studio_loop(client: OpenAI | None, skip_path: str | None,
                out_dir: Path, with_text: bool) -> None:
    scene    = DEFAULT_SCENE
    approved = False

    while not approved:
        prompt = COVER_PROMPT_TEMPLATE.format(scene=scene)

        if skip_path:
            print(f"\n  Loading raw cover: {skip_path}")
            raw = Image.open(skip_path).convert("RGB")
            skip_path = None   # only use once
        else:
            print(f"\n  Generating cover illustration…")
            print(f"  Scene: {scene[:80]}…")
            raw = generate_cover_image(prompt, client)

            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            raw_path = out_dir / f"cover_{ts}_raw.png"
            raw.save(raw_path)
            print(f"  → Raw saved: {raw_path}")

        print("  Binarizing + upscaling…")
        proc  = binarize(raw)
        cover = upscale_to_cover(proc)

        if with_text:
            cover = inject_cover_text(cover)

        ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
        prev_path  = out_dir / f"cover_{ts}_preview.png"
        cover.save(prev_path, dpi=(OUTPUT_DPI, OUTPUT_DPI))
        print(f"\n  Preview saved: {prev_path}")
        print(f"  Open it to review, then choose:")
        print(f"    [A] Approva e salva come cover finale")
        print(f"    [R] Rigenera (stesso scene)")
        print(f"    [M] Modifica scene description")
        print(f"    [Q] Esci senza salvare")

        choice = input("\n  Scelta [A/R/M/Q]: ").strip().upper()

        if choice == "A":
            final_path = out_dir / "cover_FINAL.png"
            cover.save(final_path, dpi=(OUTPUT_DPI, OUTPUT_DPI))
            size_mb = final_path.stat().st_size / 1e6
            print(f"\n  ✓  Cover approvata: {final_path}  ({size_mb:.1f} MB)")
            approved = True

        elif choice == "R":
            print("  Rigenerando…")

        elif choice == "M":
            print(f"\n  Scene attuale:\n  {scene}\n")
            new_scene = input("  Nuova scene description: ").strip()
            if new_scene:
                scene = new_scene

        elif choice == "Q":
            print("  Uscita senza salvare cover finale.")
            sys.exit(0)

        else:
            print("  Scelta non riconosciuta — premi A, R, M o Q.")


def main() -> None:
    print(
        "studio_mode.py is DEPRECATED.\n"
        "  - Cover composition has moved to cover_builder.py (correct KDP wrap math + spine + barcode area).\n"
        "  - Interactive UI has moved to the Streamlit app's 'Studio Mode' tab (run: streamlit run app.py).\n"
        "  - This script will be removed in a future release.\n",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
