#!/usr/bin/env python3
"""
Assembles the final KDP-ready PDF.

Page order (target = 65 pages):
  1.    QR code page
  2.    Frontespizio ("This Book Belongs To")
  3.    Test Your Colors
  4-63. 30 illustrations × (illustration + black anti-bleed page)
  64.   Review request (back matter)
  65.   Collection cross-sell (back matter)

Usage:
    python pdf_assembler.py --lang it --output zodiacale_v1.pdf
    python pdf_assembler.py --lang en --target-pages 65
    python pdf_assembler.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from zodiac_config import SIGN_ORDER

KDP_W, KDP_H = 2550, 3300
OUTPUT_DPI = 300
TARGET_ILLUSTRATIONS = 30
TARGET_PAGES = 3 + TARGET_ILLUSTRATIONS * 2 + 2  # 65

SPECIAL_DIR = Path("output/special")
PAGES_DIR = Path("output/pages")
FINAL_DIR = Path("output/final")


def _all_finals_for_sign(sign: str) -> list[Path]:
    """All `_final.png` for a sign, sorted by name (deterministic)."""
    return sorted(PAGES_DIR.glob(f"{sign}_*_final.png"))


def collect_pages(lang: str, target_illustrations: int = TARGET_ILLUSTRATIONS,
                  dry_run: bool = False) -> list[Path]:
    """Build the ordered manifest. Cycles through SIGN_ORDER taking 1
    illustration per sign per pass until `target_illustrations` is reached."""
    pages: list[Path] = []
    missing: list[str] = []

    special_files = {
        "qr": SPECIAL_DIR / "01_qr_code.png",
        "frontespizio": SPECIAL_DIR / "02_frontespizio.png",
        "test_colors": SPECIAL_DIR / "03_test_colors.png",
        "black": SPECIAL_DIR / "black_separator.png",
        "review": SPECIAL_DIR / "98_review.png",
        "collection": SPECIAL_DIR / "99_collection.png",
    }

    for key in ("qr", "frontespizio", "test_colors"):
        path = special_files[key]
        if path.exists():
            pages.append(path)
        else:
            missing.append(str(path))

    black_sep = special_files["black"]

    # Per-sign queues of available illustrations
    queues: dict[str, list[Path]] = {sign: _all_finals_for_sign(sign) for sign in SIGN_ORDER}
    selected: list[Path] = []
    # Round-robin over signs until we hit target_illustrations or run out
    while len(selected) < target_illustrations:
        progress = False
        for sign in SIGN_ORDER:
            if len(selected) >= target_illustrations:
                break
            q = queues[sign]
            if q:
                selected.append(q.pop(0))
                progress = True
        if not progress:
            break

    if len(selected) < target_illustrations:
        missing.append(
            f"only {len(selected)}/{target_illustrations} illustration files available "
            f"under {PAGES_DIR}/"
        )

    for img_path in selected:
        pages.append(img_path)
        if black_sep.exists():
            pages.append(black_sep)
        else:
            missing.append(f"black separator (needed after {img_path.name})")

    for key in ("review", "collection"):
        path = special_files[key]
        if path.exists():
            pages.append(path)
        else:
            missing.append(str(path))

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


def qc_report(pages: list[Path], target: int = TARGET_PAGES) -> dict:
    """Pre-assembly QC: page count, size, mode."""
    report = {
        "target": target,
        "actual": len(pages),
        "ok": len(pages) == target,
        "issues": [],
    }
    for p in pages:
        try:
            with Image.open(p) as img:
                if img.size != (KDP_W, KDP_H):
                    report["issues"].append(f"{p.name}: size {img.size} != {(KDP_W, KDP_H)}")
        except Exception as e:
            report["issues"].append(f"{p.name}: open failed: {e}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="The Daily KDP Press — PDF Assembler")
    parser.add_argument("--lang", default="it", choices=["it", "en"])
    parser.add_argument("--output", default=None,
                        help="Output filename (default: zodiacale_v1.pdf)")
    parser.add_argument("--target-illustrations", type=int, default=TARGET_ILLUSTRATIONS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output_name = Path(args.output or f"zodiacale_{args.lang}_v1.pdf").name  # path-traversal guard
    output_path = FINAL_DIR / output_name

    target_pages = 3 + args.target_illustrations * 2 + 2
    print(f"\n{'='*55}")
    print(f"  The Daily KDP Press — PDF Assembler")
    print(f"  Lang: {args.lang} | Target: {target_pages} pages | Out: {output_path}")
    print(f"{'='*55}")

    pages = collect_pages(args.lang, target_illustrations=args.target_illustrations,
                          dry_run=args.dry_run)
    qc = qc_report(pages, target=target_pages)
    print(f"\n  QC: {qc['actual']}/{qc['target']} pages "
          f"({'OK' if qc['ok'] else 'INCOMPLETE'})")
    if qc["issues"]:
        print(f"  Issues: {len(qc['issues'])}")
        for issue in qc["issues"][:10]:
            print(f"    - {issue}")

    if args.dry_run:
        print(f"\n  Page order ({len(pages)} files):")
        for i, p in enumerate(pages, 1):
            print(f"  [{i:03d}] {p}")
        print(f"\n  Dry run complete. No PDF written.")
        return

    assemble_pdf(pages, output_path)


if __name__ == "__main__":
    main()
