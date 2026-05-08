import json
import urllib.request
import urllib.error
from typing import Optional

FOOTER = """
<div style="margin-top:40px;padding-top:20px;border-top:1px solid #2a2a3e;text-align:center;font-size:12px;color:#666;">
  <p>The Daily Burnout Press — Zodiaco Esaurito</p>
  <p><a href="{{unsubscribe}}" style="color:#e94560;text-decoration:none;">Disiscriviti dalla lista</a></p>
</div>
"""

def _wrap_html(content: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ margin:0; padding:0; background:#0f0f1a; font-family:sans-serif; color:#e0e0e0; }}
  .container {{ max-width:600px; margin:0 auto; padding:30px 20px; }}
  h1,h2 {{ color:#e94560; }}
  a {{ color:#e94560; }}
  .cta {{ display:inline-block; background:#e94560; color:#fff !important;
          padding:14px 28px; border-radius:6px; text-decoration:none;
          font-weight:bold; margin:20px 0; }}
  p {{ line-height:1.7; }}
  blockquote {{ border-left:3px solid #e94560; margin:20px 0; padding:10px 20px;
                background:#1a1a2e; border-radius:0 6px 6px 0; font-style:italic; }}
</style>
</head>
<body>
<div class="container">
{content}
{FOOTER}
</div>
</body>
</html>"""


SEQUENCE = [
    {
        "day": 0,
        "subject": "Il tuo bonus ti aspetta 🎁",
        "html_body": _wrap_html("""
<h1>Benvenuto nel club dei bruciati ✨</h1>
<p>Grazie per aver acquistato <strong>Zodiaco Esaurito</strong>.</p>
<p>Come promesso, ecco il tuo bonus esclusivo:</p>
<a href="{{BONUS_URL}}" class="cta">Scarica il tuo bonus gratuito</a>
<p>Nel bonus troverai contenuti extra che non sono nel libro: riflessioni più profonde,
   esercizi pratici e qualche segreto cosmico che il tuo segno preferisce tenere nascosto.</p>
<p>Nei prossimi giorni ti scriverò ancora — non spam, promesso.
   Solo cose che potrebbero farti pensare (o ridere di te stesso).</p>
<p>A presto,<br><strong>The Daily Burnout Press</strong></p>
""", "Il tuo bonus ti aspetta"),
    },
    {
        "day": 1,
        "subject": "Il tuo segno zodiacale ti descrive davvero?",
        "html_body": _wrap_html("""
<h2>Una domanda scomoda</h2>
<p>Quante volte hai letto la descrizione del tuo segno e hai pensato:<br>
<em>"Oddio, questo sono io al 100%."</em></p>
<p>E quante volte invece hai pensato:<br>
<em>"Questo non c'entra niente con me."</em></p>
<p>La verità è che tutti e due i momenti sono reali. E questo è esattamente il punto.</p>
<p>L'astrologia funziona non perché le stelle controllino il tuo destino,
   ma perché ti obbliga a farti delle domande su chi sei — e chi vorresti essere.</p>
<p>Nel libro c'è un test: 12 domande, una per ogni segno.
   Se non l'hai ancora fatto, vai a pagina 47. Potresti sorprenderti.</p>
<p>Cosa hai scoperto? Rispondi a questa email, leggo tutto.</p>
<p>— The Daily Burnout Press</p>
""", "Il tuo segno zodiacale ti descrive?"),
    },
    {
        "day": 3,
        "subject": "Hai già sentito del secondo volume?",
        "html_body": _wrap_html("""
<h2>Il seguito che non sapevi di volere</h2>
<p>Il primo volume di <strong>Zodiaco Esaurito</strong> copriva le basi:
   i 12 segni, i loro vizi, le loro ossessioni segrete.</p>
<p>Ma c'era una cosa che non riuscivamo a infilare senza sforare 300 pagine:
   <strong>le compatibilità</strong>. Non quelle romantiche — quelle <em>lavorative</em>.</p>
<p>Chi dovresti assumere per non impazzire. Chi NON dovresti mai mettere nello stesso team.
   E perché certe riunioni sembrano progettate apposta per farti perdere la voglia di vivere.</p>
<p>Il secondo volume è già disponibile su Amazon:</p>
<a href="https://www.amazon.it" class="cta">Scopri Zodiaco Esaurito Vol. 2</a>
<p>Se ti è piaciuto il primo, il secondo è peggio. Nel senso migliore.</p>
<p>— The Daily Burnout Press</p>
""", "Il secondo volume"),
    },
    {
        "day": 5,
        "subject": "Cosa dicono gli altri lettori (non è quello che ti aspetti)",
        "html_body": _wrap_html("""
<h2>Le recensioni oneste</h2>
<p>Abbiamo raccolto alcuni messaggi dai lettori. Eccone tre:</p>
<blockquote>
  "L'ho comprato come regalo ironico per mia sorella Scorpione.
   Lo ha letto in un giorno. Ora non mi parla più. 5 stelle."<br>
  <strong>— Marco R., Toro</strong>
</blockquote>
<blockquote>
  "Finalmente un libro sull'astrologia che non mi fa sentire in colpa per essere
   cinica. Consigliato a chiunque abbia un collega Gemelli insopportabile."<br>
  <strong>— Federica L., Vergine</strong>
</blockquote>
<blockquote>
  "Ho riconosciuto mio marito in ogni pagina della sezione Ariete.
   Gliel'ho messo sotto il cuscino. Ha dormito benissimo."<br>
  <strong>— Luisa M., Cancro</strong>
</blockquote>
<p>Se anche tu hai una storia simile, lascia una recensione su Amazon —
   aiuta lettori come te a trovarlo.</p>
<a href="https://www.amazon.it" class="cta">Lascia una recensione</a>
<p>— The Daily Burnout Press</p>
""", "Cosa dicono i lettori"),
    },
    {
        "day": 7,
        "subject": "L'ultima cosa prima di salutarci",
        "html_body": _wrap_html("""
<h2>Una settimana insieme</h2>
<p>È passata una settimana dal tuo acquisto. Spero che il libro (e il bonus)
   ti abbiano dato almeno un momento in cui hai pensato: <em>"Ah, quindi non sono solo io."</em></p>
<p>Prima di chiudere questa sequenza, due cose:</p>
<p><strong>1. Il pacchetto completo</strong><br>
   Se vuoi approfondire ancora, il bundle con entrambi i volumi + il workbook esclusivo
   è disponibile a prezzo speciale per i lettori già registrati:</p>
<a href="https://www.amazon.it" class="cta">Vedi il bundle completo</a>
<p><strong>2. La newsletter</strong><br>
   Una volta al mese mando una newsletter con nuovi contenuti: segni del mese,
   nuove uscite, retroscena editoriali. Nessuno spam, nessuna roba inutile.</p>
<p>Se non vuoi più ricevere email da noi, capisco — link sotto.
   Se invece vuoi restare, non fare nulla: ti scriverò solo quando ho qualcosa di utile.</p>
<p>Grazie per aver letto.<br>
   <strong>— The Daily Burnout Press</strong></p>
""", "L'ultima cosa"),
    },
]


def _brevo_request(api_key: str, endpoint: str, payload: dict) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.brevo.com/v3/{endpoint}",
        data=data,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}


def create_automation(
    api_key: str,
    list_id: int,
    name: str = "Zodiaco Esaurito Sequence",
) -> str:
    results = []
    for i, email in enumerate(SEQUENCE, start=1):
        payload = {
            "name": f"{name} — Email {i} (Day {email['day']})",
            "subject": email["subject"],
            "htmlContent": email["html_body"],
            "sender": {"name": "The Daily Burnout Press", "email": "noreply@dailyburnoutpress.com"},
            "recipients": {"listIds": [list_id]},
            "type": "classic",
        }
        status, resp = _brevo_request(api_key, "emailCampaigns", payload)
        if 200 <= status < 300:
            results.append(f"Email {i} (day={email['day']}): OK — id={resp.get('id')}")
        else:
            results.append(f"Email {i} (day={email['day']}): ERRORE {status} — {resp}")
    return "\n".join(results)


def send_welcome_email(api_key: str, to_email: str, bonus_url: str) -> bool:
    welcome = SEQUENCE[0]
    html = welcome["html_body"].replace("{{BONUS_URL}}", bonus_url)
    payload = {
        "sender": {"name": "The Daily Burnout Press", "email": "noreply@dailyburnoutpress.com"},
        "to": [{"email": to_email}],
        "subject": welcome["subject"],
        "htmlContent": html,
    }
    status, _ = _brevo_request(api_key, "smtp/email", payload)
    return 200 <= status < 300


def _html_to_plain(html: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


if __name__ == "__main__":
    for i, email in enumerate(SEQUENCE, start=1):
        print(f"{'='*60}")
        print(f"EMAIL {i} — Day {email['day']}")
        print(f"Subject: {email['subject']}")
        print(f"{'-'*60}")
        print(_html_to_plain(email["html_body"]))
        print()
