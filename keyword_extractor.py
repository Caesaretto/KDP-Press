#!/usr/bin/env python3
"""
Amazon Keyword Extractor — uses public autosuggest endpoint.

Usage:
    python keyword_extractor.py --seed "adult coloring book" --market USA
    python keyword_extractor.py --seed "coloring book zodiac" --market IT --depth 2
"""

import argparse
import time
from urllib.parse import quote

try:
    import requests
except ImportError:
    raise ImportError("Run: pip install requests")

MARKETS: dict[str, tuple[str, str]] = {
    "USA": ("https://completion.amazon.com/api/2017/suggestions",    "ATVPDKIKX0DER"),
    "UK":  ("https://completion.amazon.co.uk/api/2017/suggestions",  "A1F83G8C2ARO7P"),
    "DE":  ("https://completion.amazon.de/api/2017/suggestions",     "A1PA6795UKMFR9"),
    "IT":  ("https://completion.amazon.it/api/2017/suggestions",     "APJ6JRA9NG5V4"),
    "PL":  ("https://completion.amazon.pl/api/2017/suggestions",     "A1C3SOZRARQ6R3"),
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def get_suggestions(keyword: str, market: str = "USA", limit: int = 11) -> list[str]:
    """Fetch autosuggest completions from Amazon for a given keyword."""
    if market not in MARKETS:
        raise ValueError(f"Unknown market: {market}. Use one of {list(MARKETS)}")

    base_url, mid = MARKETS[market]
    params = {
        "mid":    mid,
        "alias":  "aps",
        "prefix": keyword,
        "limit":  limit,
    }

    try:
        r = requests.get(base_url, params=params, headers=_HEADERS, timeout=6)
        r.raise_for_status()
        data = r.json()
        return [s["value"] for s in data.get("suggestions", [])]
    except Exception:
        return []


def expand_keywords(
    seed: str,
    market: str = "USA",
    depth: int = 1,
    delay: float = 0.08,
) -> list[str]:
    """
    Expand seed keyword using Amazon autosuggest.
    depth=1: direct suggestions only
    depth=2: suggestions + alphabet expansion (a-z suffix)
    """
    all_keywords: set[str] = set()

    direct = get_suggestions(seed, market)
    all_keywords.update(direct)

    if depth >= 2:
        for letter in "abcdefghijklmnopqrstuvwxyz":
            time.sleep(delay)
            expanded = get_suggestions(f"{seed} {letter}", market)
            all_keywords.update(expanded)

    # Filter: must contain at least one word from seed
    seed_words = set(seed.lower().split())
    filtered = [
        kw for kw in all_keywords
        if any(w in kw.lower() for w in seed_words)
    ]

    return sorted(set(filtered) | set(direct))


def main() -> None:
    parser = argparse.ArgumentParser(description="Amazon Keyword Extractor")
    parser.add_argument("--seed",   required=True, help="Seed keyword")
    parser.add_argument("--market", default="USA", choices=list(MARKETS))
    parser.add_argument("--depth",  type=int, default=1, choices=[1, 2],
                        help="1=direct suggestions, 2=alphabet expansion")
    args = parser.parse_args()

    print(f"\nExtracting keywords for: \"{args.seed}\" — market: {args.market}\n")
    keywords = expand_keywords(args.seed, args.market, args.depth)

    print(f"Found {len(keywords)} keywords:\n")
    for i, kw in enumerate(keywords, 1):
        print(f"  {i:3d}. {kw}")


if __name__ == "__main__":
    main()
