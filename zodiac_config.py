#!/usr/bin/env python3
"""
Zodiac sign configuration for The Daily KDP Press.

Each entry contains the prompt parameters for generate_page.py MASTER_PROMPT_v2:
  - en_name:         English name of the sign
  - glyph_unicode:   astrological glyph (♈♉♊♋♌♍♎♏♐♑♒♓), used in border + on-character
  - soggetto_kawaii: full English description of the kawaii chibi subject
  - thematic_prop:   1 thematic context element near the subject
  - scatter_elements: comma-separated thematic accents for the white background

Legacy aliases (simbolo_angolo, simbolo_lato) are kept for backward compatibility
with code paths that still expect the v1 schema, but the new prompt template
ignores them.
"""

ZODIAC_CONFIG: dict[str, dict] = {
    "ariete": {
        "en_name": "Aries",
        "glyph_unicode": "♈",
        "soggetto_kawaii": (
            "one adorable chibi kawaii ram with big curly horns, chubby rounded body, "
            "big round sparkly eyes with white highlights, small curved smile, two tiny "
            "round blush cheeks, standing proudly on a small patch of grass"
        ),
        "thematic_prop": "a small stylized flame curl behind the ram",
        "scatter_elements": "small 5-pointed stars, tiny flame swirls, small cute clouds",
        # legacy v1
        "simbolo_angolo": "Aries ram horns ♈ stylized decorative element",
        "simbolo_lato": "small cute ram head with curved horns",
    },
    "toro": {
        "en_name": "Taurus",
        "glyph_unicode": "♉",
        "soggetto_kawaii": (
            "one adorable chibi kawaii bull with small cute round horns, chubby rounded "
            "body, big gentle round eyes, small smile, two tiny round blush cheeks, "
            "sitting contentedly with crossed front legs"
        ),
        "thematic_prop": "a small flower with rounded petals near the bull",
        "scatter_elements": "small daisies, tiny rounded leaves, small 5-pointed stars",
        "simbolo_angolo": "Taurus bull horns ♉ stylized decorative element",
        "simbolo_lato": "small cute bull face with horns and flower",
    },
    "gemelli": {
        "en_name": "Gemini",
        "glyph_unicode": "♊",
        "soggetto_kawaii": (
            "two identical chibi kawaii twin figures side by side as mirror images, "
            "matching outfits, head-to-body ratio 1:1, big round eyes with white "
            "highlights, small curved smiles, two tiny round blush cheeks each, "
            "holding hands in the center"
        ),
        "thematic_prop": "a small stylized cloud beneath them",
        "scatter_elements": "small 5-pointed stars, tiny hearts, small swirly air gusts",
        "simbolo_angolo": "Gemini twins ♊ stylized decorative element",
        "simbolo_lato": "small cute star with a face",
    },
    "cancro": {
        "en_name": "Cancer",
        "glyph_unicode": "♋",
        "soggetto_kawaii": (
            "one adorable chibi kawaii crab with big round eyes and white highlights, "
            "two tiny round blush cheeks, small smile, tiny rounded claws raised up "
            "happily, sitting inside a cute scalloped seashell"
        ),
        "thematic_prop": "a small crescent moon shape above the crab",
        "scatter_elements": "small water droplets, tiny bubbles, small 5-pointed stars",
        "simbolo_angolo": "Cancer crab ♋ stylized decorative element",
        "simbolo_lato": "small cute crab claw",
    },
    "leone": {
        "en_name": "Leo",
        "glyph_unicode": "♌",
        "soggetto_kawaii": (
            "one majestic but adorable chibi kawaii lion with a big fluffy round mane "
            "drawn as wavy petal shapes, sitting regally, big proud round eyes with "
            "white highlights, small curved smile, two tiny round blush cheeks, "
            "wearing a tiny crown"
        ),
        "thematic_prop": "a small sun with simple ray lines behind the lion",
        "scatter_elements": "small 5-pointed stars, tiny flame swirls, small crowns",
        "simbolo_angolo": "Leo lion mane ♌ stylized decorative element",
        "simbolo_lato": "small cute crown with stars",
    },
    "vergine": {
        "en_name": "Virgo",
        "glyph_unicode": "♍",
        "soggetto_kawaii": (
            "one cute chibi kawaii maiden character with neat braided hair, head-to-body "
            "ratio 1:1, big round eyes with white highlights, small smile, two tiny round "
            "blush cheeks, holding a small bouquet of three flowers, neat tidy posture"
        ),
        "thematic_prop": "a small wheat sheaf bundle beside her",
        "scatter_elements": "small flowers, tiny leaves, small 5-pointed stars",
        "simbolo_angolo": "Virgo maiden ♍ stylized decorative element",
        "simbolo_lato": "small cute wheat sheaf or flower",
    },
    "bilancia": {
        "en_name": "Libra",
        "glyph_unicode": "♎",
        "soggetto_kawaii": (
            "one adorable chibi kawaii character holding up a tiny cute balance scale "
            "with both sides perfectly equal, head-to-body ratio 1:1, big thoughtful "
            "round eyes with white highlights, small smile, two tiny round blush cheeks"
        ),
        "thematic_prop": "a small feather floating beside the scale",
        "scatter_elements": "small 5-pointed stars, tiny feathers, small hearts",
        "simbolo_angolo": "Libra scales ♎ stylized decorative element",
        "simbolo_lato": "small cute balance scale",
    },
    "scorpione": {
        "en_name": "Scorpio",
        "glyph_unicode": "♏",
        "soggetto_kawaii": (
            "one adorable chibi kawaii scorpion with a curled tail ending in a small "
            "heart shape, big intense but cute round eyes with white highlights, small "
            "mysterious smile, two tiny round blush cheeks, body in profile"
        ),
        "thematic_prop": "a small crescent moon above the scorpion",
        "scatter_elements": "small 5-pointed stars, tiny hearts, small crescent moons",
        "simbolo_angolo": "Scorpio scorpion ♏ stylized decorative element",
        "simbolo_lato": "small cute scorpion with heart tail",
    },
    "sagittario": {
        "en_name": "Sagittarius",
        "glyph_unicode": "♐",
        "soggetto_kawaii": (
            "one cute chibi kawaii centaur character (cute pony lower body, chibi person "
            "upper body), big round eyes with white highlights, small smile, two tiny "
            "round blush cheeks, holding a small bow with one tiny arrow, adventurous pose"
        ),
        "thematic_prop": "a small target circle in the background",
        "scatter_elements": "small 5-pointed stars, tiny arrows, small feathers",
        "simbolo_angolo": "Sagittarius arrow ♐ stylized decorative element",
        "simbolo_lato": "small cute arrow with feathers",
    },
    "capricorno": {
        "en_name": "Capricorn",
        "glyph_unicode": "♑",
        "soggetto_kawaii": (
            "one adorable chibi kawaii mountain goat with tiny curved horns, chubby "
            "rounded body, big determined round eyes with white highlights, small smile, "
            "two tiny round blush cheeks, standing on top of a small rounded mountain peak"
        ),
        "thematic_prop": "small simple mountain silhouettes behind",
        "scatter_elements": "small 5-pointed stars, tiny snowflakes, small rounded peaks",
        "simbolo_angolo": "Capricorn sea-goat ♑ stylized decorative element",
        "simbolo_lato": "small cute mountain peak with star",
    },
    "acquario": {
        "en_name": "Aquarius",
        "glyph_unicode": "♒",
        "soggetto_kawaii": (
            "one cute chibi kawaii boy in a Greek tunic sitting on a fluffy round cloud, "
            "head-to-body ratio 1:1, big round eyes with white highlights, small smile, "
            "two tiny round blush cheeks, holding a tilted star-decorated amphora that "
            "pours stylized water waves downward"
        ),
        "thematic_prop": "a small fluffy cloud beside the main cloud",
        "scatter_elements": "small clouds, stylized water drop swirls, small 5-pointed stars",
        "simbolo_angolo": "Aquarius water waves ♒ stylized decorative element",
        "simbolo_lato": "small cute water jug pouring stars",
    },
    "pesci": {
        "en_name": "Pisces",
        "glyph_unicode": "♓",
        "soggetto_kawaii": (
            "two adorable chibi kawaii fish in a yin-yang circular arrangement (one "
            "ascending, one descending), each with big round eyes with white highlights, "
            "small curved smile, two tiny round blush cheeks, detailed scales drawn as "
            "uniform repeated curves, detailed pinned fins"
        ),
        "thematic_prop": "a small stylized lotus flower below the fish",
        "scatter_elements": "small water droplets, tiny lotus petals, small 5-pointed stars",
        "simbolo_angolo": "Pisces fish ♓ stylized decorative element",
        "simbolo_lato": "small cute fish with heart bubble",
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
