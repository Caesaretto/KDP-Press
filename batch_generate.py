#!/usr/bin/env python3
"""
Batch generation of all 12 zodiac coloring pages.

Usage:
    python batch_generate.py --lang it
    python batch_generate.py --lang en --sign leone
    python batch_generate.py --lang it --dry-run
"""

import argparse
import subprocess
import sys
from pathlib import Path

from frasi_zodiacali import FRASI
from zodiac_config import SIGN_ORDER

COST_PER_IMAGE = 0.04  # gpt-image-1 high quality, USD


def run_sign(sign: str, phrase: str, lang: str, out_dir: str) -> bool:
    cmd = [
        sys.executable, "generate_page.py",
        sign, phrase, lang,
        "--out-dir", out_dir,
    ]
    result = subprocess.run(cmd)
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="The Daily KDP Press — Batch Generator")
    parser.add_argument("--lang",    default="it", choices=["it", "en"], help="Output language")
    parser.add_argument("--sign",    default=None, help="Generate only this sign")
    parser.add_argument("--out-dir", default="output/pages")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without calling API")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    signs = [args.sign] if args.sign else SIGN_ORDER
    jobs: list[tuple[str, str]] = []

    for sign in signs:
        phrases = FRASI.get(sign, {}).get(args.lang, [])
        if not phrases:
            print(f"  SKIP {sign}: no phrases for lang={args.lang}")
            continue
        for phrase in phrases:
            jobs.append((sign, phrase))

    total      = len(jobs)
    est_cost   = total * COST_PER_IMAGE

    print(f"\n{'='*55}")
    print(f"  The Daily KDP Press — Batch Generator")
    print(f"  {total} image(s) | lang={args.lang} | est. cost ~${est_cost:.2f}")
    print(f"{'='*55}\n")

    if args.dry_run:
        for i, (sign, phrase) in enumerate(jobs, 1):
            print(f"  [{i:02d}/{total}] {sign:<12} | {phrase}")
        print(f"\n  Dry run complete. No API calls made.")
        return

    ok = 0
    for i, (sign, phrase) in enumerate(jobs, 1):
        print(f"\n[{i:02d}/{total}] {sign.upper()} — \"{phrase}\"")
        if run_sign(sign, phrase, args.lang, args.out_dir):
            ok += 1
        else:
            print(f"  ✗ FAILED: {sign}")

    actual_cost = ok * COST_PER_IMAGE
    print(f"\n{'='*55}")
    print(f"  Done: {ok}/{total} images generated")
    print(f"  Estimated actual cost: ~${actual_cost:.2f}")
    print(f"  Output: {out_dir.resolve()}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
