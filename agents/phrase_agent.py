"""
Phrase Agent — generates ironic Italian phrases for coloring-book pages.

Replaces the hardcoded `frasi_zodiacali.py` with an LLM call that, given a
book theme/niche/tone, produces N fresh phrases optionally assigned to
specific subjects (e.g., zodiac signs for the astrology niche).

Public API:
    generate_phrases(book_theme, niche, tone, count, lang, brief, client)
        -> list[dict]  with keys {"text": str, "subject_key": str | None}
"""
from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from zodiac_config import SIGN_ORDER


_SYSTEM_BASE = """\
Sei un copywriter esperto in editoria umoristica italiana per il mercato \
Amazon KDP, specializzato in libri da colorare per adulti della nicchia \
self-deprecation / burnout / oroscopo ironico.

Il tuo stile:
- Italiano contemporaneo, conversazionale, mai gergale
- Ironia auto-deprecante, sarcasmo dolce, mai amaro o offensivo
- Frasi corte (5-10 parole), max 12, autocontenute
- Tono che la lettrice tipica (donna 25-45 anni, già un po' stanca della \
vita quotidiana) riconoscerebbe come "questa è scritta per me"
- Le frasi vengono stampate in MAIUSCOLO sulla pagina del libro da colorare, \
quindi devono funzionare a tutte maiuscole
- Niente bestemmie, niente politica, niente body shaming, niente offensivo
- Evita cliché stantii ("Lunedì che fatica"). Cerca angolature inaspettate.
"""

_USER_GENERIC = """\
Genera esattamente {count} frasi {tone} in lingua {lang} per un libro da \
colorare intitolato "{book_theme}" della nicchia "{niche}".

{brief_block}

Vincoli ferrei:
- Massimo 12 parole per frase
- Ogni frase autocontenuta, comprensibile fuori contesto
- Nessuna duplicazione (controlla bene)
- Niente virgolette dentro la frase
- Coerenza tematica col titolo "{book_theme}"

Restituisci SOLO un JSON nella forma esatta (nient'altro):
{{"phrases": ["FRASE 1.", "FRASE 2.", ..., "FRASE {count}."]}}
"""

_USER_ZODIAC = """\
Genera esattamente {count} frasi {tone} in lingua {lang} per un libro da \
colorare zodiacale intitolato "{book_theme}".

{brief_block}

Ogni frase deve essere ASSOCIATA a uno dei 12 segni zodiacali. Distribuisci \
le {count} frasi tra i 12 segni in modo equo (alcuni segni avranno 2-3 frasi \
ciascuno). La frase deve essere PERTINENTE al carattere stereotipato del \
segno (Ariete impulsivo, Toro testardo, Gemelli incostante, Cancro \
emotivo, Leone egocentrico, Vergine perfezionista, Bilancia indecisa, \
Scorpione vendicativo, Sagittario fugace, Capricorno workaholic, Acquario \
distaccato, Pesci sognatore) MA con tono ironico/sarcastico, non oroscopo \
serio.

Vincoli:
- Massimo 12 parole per frase
- Italiano contemporaneo, all'apparenza rivolto al segno ma con sottinteso \
auto-ironico (la lettrice riconosce sé stessa o un amico)
- Nessuna duplicazione
- Niente virgolette dentro la frase
- Maiuscolo finale ok per stampa

Segni canonici (chiave da usare nel JSON):
{sign_list}

Restituisci SOLO un JSON nella forma esatta:
{{"phrases": [
  {{"sign": "ariete", "text": "FRASE PER L'ARIETE."}},
  {{"sign": "acquario", "text": "FRASE PER L'ACQUARIO."}},
  ...
]}}
"""


def generate_phrases(
    book_theme: str,
    niche: str = "astrology",
    tone: str = "ironico e sarcastico",
    count: int = 30,
    lang: str = "it",
    brief: str | None = None,
    client: OpenAI | None = None,
    model: str = "gpt-4o",
) -> list[dict[str, Any]]:
    """Generate `count` phrases for a coloring book.

    Args:
        book_theme: Book title / theme (e.g., "Zodiacale Esaurito").
        niche: Niche key (e.g., "astrology", "office_burnout"). For
            "astrology" each phrase is assigned to a zodiac sign.
        tone: Tone of voice (free-form, passed verbatim to the LLM).
        count: Number of phrases to generate.
        lang: Language code ("it" or "en").
        brief: Optional additional context from the author.
        client: OpenAI client. Created on demand if None.
        model: Chat model (default "gpt-4o").

    Returns:
        List of dicts {"text": str, "subject_key": str | None}.
        For astrology niche, `subject_key` is a zodiac sign (e.g. "acquario").
        For other niches, `subject_key` is None.

    Raises:
        RuntimeError if the LLM response is malformed or too few phrases.
    """
    if client is None:
        client = OpenAI()

    brief_block = (
        f"Contesto aggiuntivo dell'autore: {brief}\n"
        if brief and brief.strip()
        else ""
    )

    if niche == "astrology":
        user_prompt = _USER_ZODIAC.format(
            book_theme=book_theme,
            tone=tone,
            lang=lang,
            count=count,
            brief_block=brief_block,
            sign_list=", ".join(SIGN_ORDER),
        )
    else:
        user_prompt = _USER_GENERIC.format(
            book_theme=book_theme,
            niche=niche,
            tone=tone,
            lang=lang,
            count=count,
            brief_block=brief_block,
        )

    # Scale max_tokens with count: ~50 tokens per zodiac entry, plus JSON
    # overhead. Floor 1500, headroom 1.5x.
    max_tokens = max(1500, int(count * 75))

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_BASE},
            {"role": "user",   "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.9,
        max_tokens=max_tokens,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Phrase agent returned invalid JSON: {e}\nRaw response:\n{raw[:500]}"
        )

    items = data.get("phrases", [])
    if not isinstance(items, list):
        raise RuntimeError(f"Phrase agent: 'phrases' not a list: {type(items)}")

    out: list[dict[str, Any]] = []
    sign_set = set(SIGN_ORDER)

    for item in items:
        if isinstance(item, str):
            out.append({"text": item.strip(), "subject_key": None})
        elif isinstance(item, dict):
            text = (item.get("text") or item.get("phrase") or "").strip()
            sign = (item.get("sign") or item.get("subject_key") or "").strip().lower()
            if sign not in sign_set:
                sign = None
            if text:
                out.append({"text": text, "subject_key": sign})

    # For astrology, fill in any missing subject_key by cycling through signs
    if niche == "astrology":
        for i, item in enumerate(out):
            if not item["subject_key"]:
                item["subject_key"] = SIGN_ORDER[i % len(SIGN_ORDER)]

    if len(out) < max(1, count - 2):
        raise RuntimeError(
            f"Phrase agent returned only {len(out)} usable phrases "
            f"(expected ~{count})"
        )

    # Truncate to the requested count
    return out[:count]
