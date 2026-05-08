#!/usr/bin/env python3
"""
Assembles the final KDP-ready PDF from generated pages and special pages.

Page order:
  1. QR Code page
  2. Frontespizio
  3. Test your colors
  4. [Illustrazione segno] + [Pagina nera] × 12

Usage:
    python pdf_assembler.py --lang it --output burnout_zodiac_IT.pdf
    python pdf_assembler.py --lang en --output burnout_zodiac_EN.pdf
    python pdf_assembler.py --dry-run
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

from zodiac_config import SIGN_ORDER

KDP_W, KDP_H = 2550, 3300
OUTPUT_DPI   = 300

SPECIAL_DIR = Path("output/special")
PAGES_DIR   = Path("output/pages")
FINAL_DIR   = Path("output/final")


def _latest_final(sign: str, lang: str) -> Path | None:
    """Find the most recent _final.png for a given sign."""
    candidates = sorted(PAGES_DIR.glob(f"{sign}_*_final.png"))
    # Prefer lang-matched files if naming includes lang, otherwise take latest
    if not candidates:
        return None
    return candidates[-1]


def collect_pages(lang: str, dry_run: bool = False) -> list[Path]:
    """Return ordered list of page paths for the PDF."""
    pages: list[Path] = []
    missing: list[str] = []

    special_files = {
        "qr":           SPECIAL_DIR / "01_qr_code.png",
        "frontespizio": SPECIAL_DIR / "02_frontespizio.png",
        "test_colors":  SPECIAL_DIR / "03_test_colors.png",
        "black":        SPECIAL_DIR / "black_separator.png",
    }

    for key, path in special_files.items():
        if path.exists():
            pages.append(path) if key != "black" else None  # black added per-sign below
        else:
            missing.append(str(path))

    # Add illustration pages in zodiac order
    black_sep = special_files["black"]
    for sign in SIGN_ORDER:
        img_path = _latest_final(sign, lang)
        if img_path:
            pages.append(img_path)
            if black_sep.exists():
                pages.append(black_sep)
            else:
                missing.append(f"black separator (needed after {sign})")
        else:
            missing.append(f"output/pages/{sign}_*_final.png")

    if missing and not dry_run:
        print(f"\n  ⚠ Missing files ({len(missing)}):")
        for m in missing:
            print(f"    - {m}")

    return pages


def assemble_pdf(pages: list[Path], output_path: Path) -> None:
    print(f"\n  Loading {len(pages)} pages…")
    images: list[Image.Image] = []

    for i, p in enumerate(pages, 1):
        print(f"  [{i:03d}/{len(pages)}] {p.name}", flush=True)
        img = Image.open(p).convert("RGB")
        if img.size != (KDP_W, KDP_H):
            img = img.resize((KDP_W, KDP_H), Image.LANCZOS)
        images.append(img)

    if not images:
        print("  ✗ No pages to assemble.", file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"\n  Saving PDF to {output_path}…")
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        resolution=OUTPUT_DPI,
        dpi=(OUTPUT_DPI, OUTPUT_DPI),
    )
    size_mb = output_path.stat().st_size / 1e6
    print(f"  ✓  {output_path}  ({len(images)} pages | {size_mb:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="The Daily KDP Press — PDF Assembler")
    parser.add_argument("--lang",    default="it", choices=["it", "en"])
    parser.add_argument("--output",  default=None,
                        help="Output filename (default: burnout_zodiac_{LANG}.pdf)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print page list without building PDF")
    args = parser.parse_args()

    output_name = args.output or f"burnout_zodiac_{args.lang.upper()}.pdf"
    output_path = FINAL_DIR / output_name

    print(f"\n{'='*55}")
    print(f"  The Daily KDP Press — PDF Assembler")
    print(f"  Lang: {args.lang} | Output: {output_path}")
    print(f"{'='*55}")

    pages = collect_pages(args.lang, dry_run=args.dry_run)

    if args.dry_run:
        print(f"\n  Page order ({len(pages)} files):")
        for i, p in enumerate(pages, 1):
            print(f"  [{i:03d}] {p}")
        print(f"\n  Dry run complete. No PDF written.")
        return

    assemble_pdf(pages, output_path)


if __name__ == "__main__":
    main()
