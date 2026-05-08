#!/usr/bin/env python3
"""
Ironic phrases for the Zodiaco Esaurito coloring book.
2 phrases per sign, in Italian and English.
Max 8 words each. Tone: affectionate sarcasm / gag gift.
"""

FRASI: dict[str, dict[str, list[str]]] = {
    "ariete": {
        "it": [
            "Sì, hai ragione. Come sempre.",
            "Rallenta. Gli altri esistono ancora.",
        ],
        "en": [
            "Yes, you're right. As always.",
            "Slow down. Others still exist.",
        ],
    },
    "toro": {
        "it": [
            "No, non è cambiato. Esatto.",
            "Hai mangiato. Quindi stai bene.",
        ],
        "en": [
            "No, nothing changed. Correct.",
            "You ate. So you're fine.",
        ],
    },
    "gemelli": {
        "it": [
            "Quale personalità usi oggi?",
            "Decidi. Ti aspetto qui.",
        ],
        "en": [
            "Which personality today?",
            "Decide. I'll wait right here.",
        ],
    },
    "cancro": {
        "it": [
            "Non stai soffrendo. Stai recitando.",
            "Hai già pianto oggi?",
        ],
        "en": [
            "You're not suffering. You're acting.",
            "Cried today yet?",
        ],
    },
    "leone": {
        "it": [
            "No, non tutti ti stanno guardando. Forse.",
            "Il pubblico è stanco. Siediti.",
        ],
        "en": [
            "No, not everyone's watching. Maybe.",
            "The audience is tired. Sit down.",
        ],
    },
    "vergine": {
        "it": [
            "Non tutto è sbagliato. Solo il 94%.",
            "Lista completata. Rifai la lista.",
        ],
        "en": [
            "Not everything's wrong. Just 94%.",
            "List done. Redo the list.",
        ],
    },
    "bilancia": {
        "it": [
            "Scegli. Prima di domani, però.",
            "No, non è tutto relativo.",
        ],
        "en": [
            "Choose. Before tomorrow, though.",
            "No, it's not all relative.",
        ],
    },
    "scorpione": {
        "it": [
            "Stai ancora pensando a quella cosa del 2019?",
            "Perdona. Non ora, prima o poi.",
        ],
        "en": [
            "Still thinking about that 2019 thing?",
            "Forgive. Not now, eventually.",
        ],
    },
    "sagittario": {
        "it": [
            "Il piano era atterrare, però.",
            "Non tutto è un'avventura. Paga le bollette.",
        ],
        "en": [
            "The plan was to land, though.",
            "Not everything's an adventure. Pay bills.",
        ],
    },
    "capricorno": {
        "it": [
            "Esci dal lavoro. È domenica.",
            "Rilassati. Ti prometto che non muori.",
        ],
        "en": [
            "Leave work. It's Sunday.",
            "Relax. I promise you won't die.",
        ],
    },
    "acquario": {
        "it": [
            "Tranquillo, non serve essere originali.",
            "No, non ti capisce nessuno. A proposito.",
        ],
        "en": [
            "Relax, being original isn't required.",
            "No, nobody gets you. By design.",
        ],
    },
    "pesci": {
        "it": [
            "Ok, ora torna coi piedi per terra e sii logico.",
            "Non è un sogno. È lunedì.",
        ],
        "en": [
            "Ok, now be logical for once.",
            "It's not a dream. It's Monday.",
        ],
    },
}
