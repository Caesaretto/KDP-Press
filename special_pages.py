#!/usr/bin/env python3
"""
Generates the 4 fixed pages for the Zodiaco Esaurito KDP book.

Usage:
    python special_pages.py --out-dir output/special
    python special_pages.py --page qr          # single page
    python special_pages.py --page frontespizio
    python special_pages.py --page test_colors
    python special_pages.py --page black
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── KDP dimensions ────────────────────────────────────────────────────────────
KDP_W, KDP_H = 2550, 3300
OUTPUT_DPI   = 300

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

QR_PLACEHOLDER_URL = "https://thedailyburnoutpress.com/bonus"


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _centered_text(draw: ImageDraw.ImageDraw, y: int, text: str,
                   font: ImageFont.FreeTypeFont, fill: tuple = (0, 0, 0)) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (KDP_W - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, font=font, fill=fill)


def make_qr_page(url: str = QR_PLACEHOLDER_URL) -> Image.Image:
    """Page 1: QR code + gift message."""
    img  = Image.new("RGB", (KDP_W, KDP_H), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        import qrcode
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=18,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        # Center QR at 55% height
        qr_size = min(KDP_W - 400, 1400)
        qr_img  = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
        x_qr    = (KDP_W - qr_size) // 2
        y_qr    = int(KDP_H * 0.30)
        img.paste(qr_img, (x_qr, y_qr))
    except ImportError:
        # Draw a placeholder rectangle if qrcode not installed
        draw.rectangle(
            [(KDP_W // 2 - 600, int(KDP_H * 0.28)), (KDP_W // 2 + 600, int(KDP_H * 0.72))],
            outline=(0, 0, 0), width=8,
        )
        draw.text(
            (KDP_W // 2 - 200, KDP_H // 2 - 40),
            "QR CODE", font=_load_font(80), fill=(0, 0, 0),
        )
        print("  ⚠ qrcode not installed — drew placeholder. Run: pip install qrcode[pil]",
              file=sys.stderr)

    title_font = _load_font(90)
    sub_font   = _load_font(60)
    url_font   = _load_font(45)

    _centered_text(draw, int(KDP_H * 0.08), "Scansiona per 10", title_font)
    _centered_text(draw, int(KDP_H * 0.08) + 110, "illustrazioni extra esclusive", title_font)
    _centered_text(draw, int(KDP_H * 0.08) + 220, "🎁", sub_font)

    _centered_text(draw, int(KDP_H * 0.82), url, url_font, fill=(120, 120, 120))

    return img


def make_frontespizio() -> Image.Image:
    """Page 2: Ironic title page — 'This book belongs to: ___'"""
    img  = Image.new("RGB", (KDP_W, KDP_H), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    title_font = _load_font(110)
    sub_font   = _load_font(75)
    bite_font  = _load_font(60)

    # Thin decorative border
    margin = 80
    draw.rectangle(
        [(margin, margin), (KDP_W - margin, KDP_H - margin)],
        outline=(0, 0, 0), width=4,
    )
    draw.rectangle(
        [(margin + 20, margin + 20), (KDP_W - margin - 20, KDP_H - margin - 20)],
        outline=(0, 0, 0), width=2,
    )

    y = int(KDP_H * 0.30)
    _centered_text(draw, y, "Questo libro", title_font)
    _centered_text(draw, y + 140, "appartiene a:", title_font)

    # Blank line for the name
    line_y = y + 340
    line_x1, line_x2 = KDP_W // 2 - 600, KDP_W // 2 + 600
    draw.line([(line_x1, line_y), (line_x2, line_y)], fill=(0, 0, 0), width=5)

    _centered_text(draw, line_y + 80, "e se lo tocchi ti mordo.", bite_font)

    return img


def make_test_colors() -> Image.Image:
    """Page 3: Color-test grid of 12 empty circles."""
    img  = Image.new("RGB", (KDP_W, KDP_H), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    title_font = _load_font(70)
    label_font = _load_font(40)

    heading = "Prova i tuoi colori qui"
    subhead = "prima di rovinare qualcosa di bello"
    _centered_text(draw, 180, heading,  title_font)
    _centered_text(draw, 290, subhead,  label_font)

    # 4 columns × 3 rows of circles
    cols, rows  = 4, 3
    r           = 200
    pad_x       = (KDP_W - cols * (r * 2 + 60)) // 2 + r
    pad_y_start = 480
    row_gap     = (KDP_H - pad_y_start - 200) // rows

    for row in range(rows):
        for col in range(cols):
            cx = pad_x + col * (r * 2 + 60)
            cy = pad_y_start + row * row_gap + r
            draw.ellipse(
                [(cx - r, cy - r), (cx + r, cy + r)],
                outline=(0, 0, 0), width=6,
            )

    return img


def make_black_page() -> Image.Image:
    """Separator page: solid black, inserted after each illustration."""
    return Image.new("RGB", (KDP_W, KDP_H), (0, 0, 0))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

PAGE_BUILDERS = {
    "qr":           (make_qr_page,       "01_qr_code.png"),
    "frontespizio": (make_frontespizio,   "02_frontespizio.png"),
    "test_colors":  (make_test_colors,    "03_test_colors.png"),
    "black":        (make_black_page,     "black_separator.png"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="The Daily KDP Press — Special Pages")
    parser.add_argument("--out-dir", default="output/special")
    parser.add_argument("--page",    default=None,
                        choices=list(PAGE_BUILDERS.keys()),
                        help="Generate only this page (default: all)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pages = [args.page] if args.page else list(PAGE_BUILDERS.keys())

    for name in pages:
        builder, filename = PAGE_BUILDERS[name]
        print(f"  Generating {name}…", flush=True)
        img  = builder()
        path = out_dir / filename
        img.save(path, dpi=(OUTPUT_DPI, OUTPUT_DPI))
        print(f"  ✓  {path}  ({img.size[0]}×{img.size[1]})")


if __name__ == "__main__":
    main()
