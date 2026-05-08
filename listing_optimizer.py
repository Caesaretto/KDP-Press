from pathlib import Path

LISTING_IT = {
    "title": (
        "Zodiaco Esaurito - Libro da Colorare per Adulti | 12 Segni Zodiacali Kawaii | "
        "Anti-Stress Umoristico | Regalo Originale"
    ),
    "subtitle": "Il coloring book per chi ha già dato tutto — e non ne può più",
    "description": (
        "<b>Hai mai pensato che il tuo segno zodiacale ti capisca meglio del tuo terapeuta?</b>"
        "<br><br>"
        "Zodiaco Esaurito è il libro da colorare per adulti che finalmente dice la verità "
        "sui 12 segni: niente stelline romantiche, solo illustrazioni kawaii disegnate a mano "
        "e frasi che colpiscono dove fa più male — ridendo."
        "<br><br>"
        "<b>Cosa trovi dentro:</b>"
        "<ul>"
        "<li>12 illustrazioni a piena pagina, una per ogni segno — stile kawaii originale</li>"
        "<li>Frasi irriverenti in italiano per ogni segno (quelle che non puoi dire ad alta voce)</li>"
        "<li>Formato 8.5x11 pollici — pagine grandi, dettagli fini, zero scuse</li>"
        "<li>Carta di qualità, adatta a matite colorate, pennarelli e acquerelli leggeri</li>"
        "<li>Bonus digitale esclusivo via QR code: 10 illustrazioni extra + test personale</li>"
        "</ul>"
        "<b>Il regalo perfetto per:</b> chi festeggia un compleanno e non vuole un mazzo di fiori, "
        "colleghi con troppa energia, amici Gemelli che non si fermano mai, e chiunque abbia "
        "superato i 25 anni convinto di farcela."
        "<br><br>"
        "<b>By The Daily Burnout Press</b> — edizioni per chi sopravvive."
    ),
    "keywords": [
        "libro da colorare adulti zodiaco",
        "coloring book astrology kawaii italiano",
        "regalo divertente donna segno zodiacale",
        "anti stress colorare adulti umoristico",
        "libro regalo compleanno originale donna",
        "colorare adulti kawaii illustrazioni",
        "zodiaco umoristico regalo amiche",
    ],
    "categories": ["CGN004120", "CGN004040"],
}

LISTING_EN = {
    "title": (
        "Exhausted Zodiac - Adult Coloring Book | 12 Kawaii Zodiac Signs | "
        "Funny Astrology Anti-Stress Gift"
    ),
    "subtitle": "The coloring book for people who've already given everything — and have nothing left",
    "description": (
        "<b>What if your zodiac sign knew you better than your therapist?</b>"
        "<br><br>"
        "Exhausted Zodiac is the adult coloring book that finally tells the truth about all 12 signs: "
        "no fluffy horoscopes, just hand-crafted kawaii illustrations and brutally honest captions "
        "that hit where it hurts — while making you laugh."
        "<br><br>"
        "<b>Inside you'll find:</b>"
        "<ul>"
        "<li>12 full-page illustrations, one per sign — original kawaii style</li>"
        "<li>Ironic captions for each sign (the ones you think but never say out loud)</li>"
        "<li>8.5x11 inch format — large pages, fine details, no excuses</li>"
        "<li>Quality paper suitable for colored pencils, markers, and light watercolors</li>"
        "<li>Exclusive digital bonus via QR code: 10 extra illustrations + personal zodiac test</li>"
        "</ul>"
        "<b>The perfect gift for:</b> birthdays that deserve something actually funny, "
        "colleagues with too much energy, that one Gemini friend who never stops talking, "
        "and anyone over 25 who thought they had it figured out."
        "<br><br>"
        "<b>By The Daily Burnout Press</b> — publishing for survivors."
    ),
    "keywords": [
        "adult coloring book zodiac signs funny",
        "kawaii astrology coloring book gift",
        "stress relief coloring book adults humor",
        "funny zodiac gift women birthday",
        "astrology coloring book anti stress",
        "kawaii coloring pages zodiac adults",
        "zodiac humor gift book astrology fan",
    ],
    "categories": ["CGN004120", "CGN004040"],
}

_MAX_TITLE = 200
_MAX_KEYWORD = 50
_MAX_DESC = 4000


def _check(label: str, value: str, max_len: int) -> list[str]:
    warnings = []
    if len(value) > max_len:
        warnings.append(f"WARNING: {label} is {len(value)} chars (max {max_len})")
    return warnings


def generate_listing_report(output_path: str = "output/listing_report.txt") -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    warnings = []
    lines = []

    for lang, listing in [("IT 🇮🇹", LISTING_IT), ("EN 🇬🇧", LISTING_EN)]:
        lines.append(f"{'='*70}")
        lines.append(f"LISTING {lang}")
        lines.append(f"{'='*70}")

        lines.append(f"\nTITLE ({len(listing['title'])} chars):")
        lines.append(listing["title"])
        warnings += _check(f"[{lang}] title", listing["title"], _MAX_TITLE)

        lines.append(f"\nSUBTITLE:")
        lines.append(listing["subtitle"])

        import re
        plain_desc = re.sub(r"<[^>]+>", " ", listing["description"])
        plain_desc = re.sub(r"\s+", " ", plain_desc).strip()
        lines.append(f"\nDESCRIPTION ({len(listing['description'])} chars):")
        lines.append(plain_desc)
        warnings += _check(f"[{lang}] description", listing["description"], _MAX_DESC)

        lines.append(f"\nBACKEND KEYWORDS (7 × max {_MAX_KEYWORD} chars):")
        for i, kw in enumerate(listing["keywords"], 1):
            flag = " ⚠ TOO LONG" if len(kw) > _MAX_KEYWORD else ""
            lines.append(f"  {i}. [{len(kw):2d} chars] {kw}{flag}")
            if len(kw) > _MAX_KEYWORD:
                warnings.append(f"[{lang}] keyword {i} is {len(kw)} chars (max {_MAX_KEYWORD})")

        lines.append(f"\nBISAC CATEGORIES:")
        for cat in listing["categories"]:
            lines.append(f"  - {cat}")

        lines.append("")

    if warnings:
        lines.append("WARNINGS:")
        for w in warnings:
            lines.append(f"  ! {w}")
    else:
        lines.append("✓ All fields within Amazon KDP limits.")

    report = "\n".join(lines)
    Path(output_path).write_text(report, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    path = generate_listing_report()
    print(f"Report saved to: {path}\n")
    print(Path(path).read_text(encoding="utf-8"))
