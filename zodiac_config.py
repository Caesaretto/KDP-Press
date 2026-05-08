#!/usr/bin/env python3
"""
Zodiac sign configuration for The Daily KDP Press.
Each entry contains the three prompt parameters for generate_page.py.
"""

ZODIAC_CONFIG: dict[str, dict] = {
    "ariete": {
        "en_name": "Aries",
        "simbolo_angolo": "Aries ram horns ♈ stylized decorative element",
        "simbolo_lato": "small cute ram head with curved horns",
        "soggetto_kawaii": "one adorable kawaii ram with big curly horns, chubby body, big sparkly eyes, determined happy expression, standing proudly",
    },
    "toro": {
        "en_name": "Taurus",
        "simbolo_angolo": "Taurus bull horns ♉ stylized decorative element",
        "simbolo_lato": "small cute bull face with horns and flower",
        "soggetto_kawaii": "one adorable kawaii bull with small cute horns, chubby body, big gentle eyes, sitting contentedly surrounded by tiny flowers",
    },
    "gemelli": {
        "en_name": "Gemini",
        "simbolo_angolo": "Gemini twins ♊ stylized decorative element",
        "simbolo_lato": "small cute star with a face",
        "soggetto_kawaii": "two identical cute kawaii chibi figures side by side, mirror images of each other, both with big eyes and happy smiles, holding hands",
    },
    "cancro": {
        "en_name": "Cancer",
        "simbolo_angolo": "Cancer crab ♋ stylized decorative element",
        "simbolo_lato": "small cute crab claw",
        "soggetto_kawaii": "one adorable kawaii crab with big round eyes, tiny claws raised up, happy expression, sitting inside a cute shell",
    },
    "leone": {
        "en_name": "Leo",
        "simbolo_angolo": "Leo lion mane ♌ stylized decorative element",
        "simbolo_lato": "small cute crown with stars",
        "soggetto_kawaii": "one majestic but adorable kawaii lion with a big fluffy round mane, sitting regally, big proud happy eyes, tiny crown on head",
    },
    "vergine": {
        "en_name": "Virgo",
        "simbolo_angolo": "Virgo maiden ♍ stylized decorative element",
        "simbolo_lato": "small cute wheat sheaf or flower",
        "soggetto_kawaii": "one cute kawaii maiden figure with neat hair holding a small bouquet of flowers, organized and tidy appearance, gentle smile",
    },
    "bilancia": {
        "en_name": "Libra",
        "simbolo_angolo": "Libra scales ♎ stylized decorative element",
        "simbolo_lato": "small cute balance scale",
        "soggetto_kawaii": "one adorable kawaii figure holding a tiny cute balance scale, both sides perfectly equal, thoughtful happy expression",
    },
    "scorpione": {
        "en_name": "Scorpio",
        "simbolo_angolo": "Scorpio scorpion ♏ stylized decorative element",
        "simbolo_lato": "small cute scorpion with heart tail",
        "soggetto_kawaii": "one adorable kawaii scorpion with a curled tail ending in a heart shape, intense but cute big eyes, mysterious smile",
    },
    "sagittario": {
        "en_name": "Sagittarius",
        "simbolo_angolo": "Sagittarius arrow ♐ stylized decorative element",
        "simbolo_lato": "small cute arrow with feathers",
        "soggetto_kawaii": "one cute kawaii centaur chibi (half cute horse half cute person) holding a tiny bow and arrow, adventurous happy expression",
    },
    "capricorno": {
        "en_name": "Capricorn",
        "simbolo_angolo": "Capricorn sea-goat ♑ stylized decorative element",
        "simbolo_lato": "small cute mountain peak with star",
        "soggetto_kawaii": "one adorable kawaii mountain goat with tiny curved horns, determined ambitious expression, standing on top of a cute small mountain",
    },
    "acquario": {
        "en_name": "Aquarius",
        "simbolo_angolo": "Aquarius water waves ♒ stylized decorative element",
        "simbolo_lato": "small cute water jug pouring stars",
        "soggetto_kawaii": "one cute kawaii figure sitting on a cloud pouring water from a decorated jug, water flowing as sparkly stars and waves below",
    },
    "pesci": {
        "en_name": "Pisces",
        "simbolo_angolo": "Pisces fish ♓ stylized decorative element",
        "simbolo_lato": "small cute fish with heart bubble",
        "soggetto_kawaii": "two adorable kawaii fish swimming in opposite directions in a yin-yang circular arrangement, both with big cute eyes and happy smiles, tiny hearts and bubbles around them",
    },
}

_ALIASES: dict[str, str] = {
    "aries": "ariete",
    "taurus": "toro",
    "gemini": "gemelli",
    "cancer": "cancro",
    "leo": "leone",
    "virgo": "vergine",
    "libra": "bilancia",
    "scorpio": "scorpione",
    "sagittarius": "sagittario",
    "capricorn": "capricorno",
    "aquarius": "acquario",
    "pisces": "pesci",
}

SIGN_ORDER = [
    "ariete", "toro", "gemelli", "cancro", "leone", "vergine",
    "bilancia", "scorpione", "sagittario", "capricorno", "acquario", "pesci",
]


def resolve(sign: str) -> str | None:
    """Return the canonical Italian key for any sign name, or None if unknown."""
    key = sign.lower()
    return _ALIASES.get(key, key) if key in ZODIAC_CONFIG or key in _ALIASES else None
