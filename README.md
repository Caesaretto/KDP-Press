# KDP-Press — The Daily Burnout Press

Pipeline editoriale digitale per generare e pubblicare libri da colorare per
adulti su Amazon KDP (categoria *Gag Gifts* / *Humor*). Stack: Python +
Streamlit per la fabbrica, Netlify per la landing page + email funnel Brevo.

Vedi [`MASTERPLAN_KDP.md`](MASTERPLAN_KDP.md) per analisi di mercato, strategia
backend e roadmap di pubblicazione.

## Componenti

| Layer | File | Cosa fa |
|---|---|---|
| Streamlit app | `app.py` | UI completa: dashboard nicchie, book builder, studio mode, export PDF, marketing tools |
| Generatore immagini | `generate_page.py` | gpt-image-1 → thresholding B&N puro → upscaling KDP 2550×3300 |
| Batch | `batch_generate.py` | Genera tutte le illustrazioni di una nicchia in un colpo |
| Front/back matter | `special_pages.py` | QR, "Belongs To", Test Colors, separatore nero, review, collection |
| Assemblatore PDF | `pdf_assembler.py` | 65 pagine KDP-ready (8.5×11" @ 300 DPI) |
| Listing | `listing_optimizer.py` + `keyword_extractor.py` | Copy IT/EN + scraping Amazon Suggest |
| A+ Content | `aplus_generator.py` | 5 moduli 970×600 per Amazon A+ |
| Landing page | `landing_page_generator.py` + `landing/` | Bundle ZIP GDPR-compliant + Netlify Function `/api/subscribe` |
| Email funnel | `email_sequence.py` + `brevo_smoke_test.py` | Brevo: DOI, soap opera 5 giorni via event |

## Setup locale

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # poi compila le chiavi
streamlit run app.py
```

Python 3.10+ raccomandato.

## Variabili d'ambiente

| Variabile | Dove serve | Note |
|---|---|---|
| `OPENAI_API_KEY` | App Streamlit + `generate_page.py` | gpt-image-1, ~$0.04/immagine |
| `BREVO_API_KEY` | `email_sequence.py`, `brevo_smoke_test.py`, Netlify Function | Brevo dashboard → SMTP & API → Generate new key |
| `BREVO_LIST_ID` | idem | ID numerico della lista marketing |
| `BREVO_DOI_TEMPLATE_ID` | `email_sequence.py` (`add_contact_doi`) | ID del template Brevo "Double Opt-In" |
| `BREVO_DOI_REDIRECT_URL` | idem | URL post-conferma (es. `/landing/thank-you.html`) |
| `BREVO_SENDER_EMAIL` | `send_template_email` | Email mittente verificata DKIM/SPF |
| `BREVO_TEMPLATE_IDS` | docs / runtime | JSON `{"welcome":N,...}` (5 template per la soap opera) |
| `ALLOWED_ORIGIN` | Netlify Function | Origin allow-list per CORS, separati da virgola |

**Mai committare la `.env`.** Già in `.gitignore`.

## Pipeline produzione libro

```bash
# 1. Front + back matter (una volta)
python special_pages.py --out-dir output/special

# 2. 30 illustrazioni della nicchia Zodiaco
python batch_generate.py --lang it
# (~30 minuti, ~$1.20 di API)

# 3. Assemblaggio PDF KDP-ready (65 pagine, 8.5x11" @ 300 DPI)
python pdf_assembler.py --lang it --output zodiacale_v1.pdf
# Output: output/final/zodiacale_v1.pdf
```

QC automatico in `pdf_assembler.py` verifica page-count target = 65 e dimensioni
ogni pagina = 2550×3300.

## Deploy Streamlit (raccomandato: Streamlit Community Cloud)

1. Push del repo su GitHub (privato OK)
2. share.streamlit.io → New app → connetti il repo, branch `main`, file `app.py`
3. Settings → Secrets → incolla in formato TOML:
   ```toml
   OPENAI_API_KEY = "sk-..."
   ```
4. Deploy. URL pubblico: `https://<user>-kdp-press.streamlit.app`

Alternative: HF Spaces (richiede `Dockerfile`), Railway (~$5/mese, persistente).

## Deploy landing page (Netlify)

1. Netlify → Add new site → Import existing project → connetti repo
2. Build settings: lascia di default, `netlify.toml` in repo è completo
3. Site settings → Environment variables:
   - `BREVO_API_KEY`
   - `BREVO_LIST_ID`
   - `ALLOWED_ORIGIN` (es. `https://thedailyburnoutpress.com,https://www.thedailyburnoutpress.com`)
4. Deploy. La function `/api/subscribe` è automaticamente esposta.
5. Configura il dominio custom (Netlify → Domain management).
6. Verifica: `curl -X POST https://YOUR_SITE/api/subscribe -H 'Content-Type: application/json' -d '{"email":"test@example.com","source":"smoke"}'` → 200.

## Setup Brevo (manuale, una tantum)

1. Account Brevo → SMTP & API → Generate new key → copia in `.env` come `BREVO_API_KEY`
2. Contatti → Liste → crea "KDP Newsletter" → copia ID in `BREVO_LIST_ID`
3. Templates → Email templates:
   - Crea template "DOI Confirmation" → copia ID in `BREVO_DOI_TEMPLATE_ID`
   - Crea 5 template per la soap opera: `welcome`, `burnout_story`, `review_request`, `pdf_bundle`, `merch_pitch` → IDs in `BREVO_TEMPLATE_IDS` (JSON)
4. Automazione → Crea workflow → trigger "Event sent" con nome `soap_opera_enroll` → 5 step a +0/+1/+2/+3/+4 giorni, ognuno invia il template corrispondente
5. Senders & IP → Verifica dominio (DKIM/SPF) per `BREVO_SENDER_EMAIL`
6. Test: `python brevo_smoke_test.py` (no invii, solo auth + list lookup)

## Checklist upload KDP (per ogni nuovo libro)

1. PDF interno pronto in `output/final/<slug>_v1.pdf` (65 pagine, 8.5×11")
2. Cover front + back + spine sul template KDP (calcolato sulle 65 pagine)
3. Listing IT/EN da `output/<slug>_listing.md`: title, bullets, description, 7 keyword backend, 2 categorie
4. A+ Content modules da `output/aplus/` (5 moduli 970×600)
5. ISBN: KDP free assignment (sufficiente per Amazon-only)
6. BISAC code: `HUM015000` (Humor / Coloring) o `CGN004120` (Crafts / Coloring)
7. Author Central bio: "The Daily Burnout Press"
8. KDP → Bookshelf → Create paperback → carica interior + cover
9. Distribuzione: Amazon (no Expanded Distribution per coloring books)
10. Pubblica → attendi 72h review → live
11. Series Linking quando avrai 3+ volumi della stessa nicchia
12. Lancio: PPC Exact Match aggressive nei primi 5 giorni (algorithmic launch velocity)

## Layout repo

```
.
├── app.py                       # Streamlit UI principale
├── generate_page.py             # Singola illustrazione AI → B&N puro
├── batch_generate.py            # Loop su tutta la nicchia
├── special_pages.py             # Front + back matter
├── pdf_assembler.py             # PDF 65 pagine KDP-ready
├── listing_optimizer.py
├── keyword_extractor.py
├── aplus_generator.py
├── landing_page_generator.py    # Genera bundle ZIP GDPR
├── email_sequence.py            # Brevo: DOI + soap opera + template send
├── brevo_smoke_test.py
├── studio_mode.py
├── niche_config.py              # 10 nicchie + prompt template
├── zodiac_config.py             # 12 segni + prompt zodiacale
├── frasi_zodiacali.py           # 30 frasi (12×2 + 6 extra)
├── landing/                     # HTML statico per Netlify
├── netlify/functions/           # Edge function /api/subscribe
├── output/                      # PDF + immagini + listing (gitignored)
├── fonts/
└── tests/                       # pytest suite
```

## Sicurezza

- `.env` e `.env.*` in `.gitignore`. Mai committare chiavi.
- `_assemble_pdf_bytes` (app.py) e `pdf_assembler.py` validano i path contro `output/{pages,special,final}` (anti path-traversal).
- `generate_page.py` accetta solo URL HTTPS verso `*.openai.com|oaiusercontent.com|azure.com` (anti-SSRF).
- Netlify Function `/api/subscribe`: rate-limit 5 req/min/IP, regex email stretto, allow-list CORS configurabile.
- Pillow pinned `>=10.3.0` (CVE-2023-50447).
- Banner cookie con tasti Accetta/Rifiuta espliciti, solo cookie tecnici.

## Testing

```bash
pip install -r requirements-dev.txt
pytest -q
```

I test coprono i moduli pure-logic (config, frasi, special_pages, pdf_assembler,
keyword/listing) con HTTP/AI mockati. Niente chiamate di rete reali.

## License

Privato. Tutti i diritti riservati a The Daily Burnout Press.
