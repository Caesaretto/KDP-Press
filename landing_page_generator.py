"""Landing page bundle generator.

Returns a ZIP (bytes) with index.html, thank-you.html, privacy.html, style.css
parametrized for the current book/campaign. The bundle is GDPR-compliant
(art. 13 disclosures, explicit Reject button, strictly-necessary cookies only)
and posts the email form to /api/subscribe (Netlify Function).
"""
from __future__ import annotations

import io
import zipfile
from html import escape
from typing import Optional


def _style_css(primary: str, accent: str, dark: bool) -> str:
    bg = "#0f0f1a" if dark else "#fafafa"
    fg = "#e0e0e0" if dark else "#1a1a1a"
    card = "#1a1a2e" if dark else "#ffffff"
    border = "#2a2a3e" if dark else "#e0e0e0"
    return f"""*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:{bg};color:{fg};font-family:system-ui,-apple-system,sans-serif;line-height:1.6}}
.container{{max-width:680px;margin:0 auto;padding:40px 20px}}
h1{{color:{accent};font-size:2.2rem;margin-bottom:12px}}
h2{{color:{primary};font-size:1.4rem;margin:24px 0 10px}}
p{{margin:12px 0}}
a{{color:{accent}}}
.card{{background:{card};border:1px solid {border};border-radius:12px;padding:28px;margin:20px 0}}
form{{display:flex;flex-direction:column;gap:12px;margin-top:20px}}
input[type=email]{{padding:14px;border:1px solid {border};border-radius:6px;background:{bg};color:{fg};font-size:1rem}}
button{{padding:14px;background:{accent};color:#fff;border:0;border-radius:6px;font-weight:bold;font-size:1rem;cursor:pointer}}
button:hover{{opacity:.9}}
.checkbox-row{{display:flex;align-items:flex-start;gap:8px;font-size:.9rem}}
.checkbox-row input{{margin-top:4px}}
.cookie-banner{{position:fixed;bottom:0;left:0;right:0;background:{card};border-top:2px solid {accent};padding:16px 20px;display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:center;z-index:1000}}
.cookie-banner button{{padding:8px 16px;font-size:.9rem;width:auto}}
.cookie-banner button.reject{{background:transparent;color:{fg};border:1px solid {border}}}
footer{{margin-top:40px;padding-top:20px;border-top:1px solid {border};text-align:center;font-size:.85rem;opacity:.7}}
.hidden{{display:none}}
"""


def _index_html(title: str, headline: str, qr_url: str, publisher: str) -> str:
    t = escape(title)
    h = escape(headline)
    p = escape(publisher)
    qr = escape(qr_url)
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{t}</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<div class="container">
<h1>{t}</h1>
<p style="font-size:1.15rem">{h}</p>
<div class="card">
<h2>Scarica il bonus gratuito</h2>
<p>Lascia la tua email e riceverai 10 illustrazioni extra + il test "Che tipo di Esaurito sei?".</p>
<form id="subscribe-form" action="/api/subscribe" method="POST">
<input type="email" name="email" placeholder="la-tua@email.it" required>
<input type="hidden" name="source" id="source-field" value="">
<div class="checkbox-row">
<input type="checkbox" name="consent" id="consent" required>
<label for="consent">Acconsento al trattamento dei dati per ricevere comunicazioni email da {p}. Leggi la <a href="privacy.html">privacy policy</a>.</label>
</div>
<button type="submit">Ricevi il bonus</button>
</form>
</div>
<footer>&copy; {p} &middot; <a href="privacy.html">Privacy</a></footer>
</div>
<div class="cookie-banner" id="cookie-banner">
<span>Usiamo solo cookie tecnici essenziali. Nessun tracciamento.</span>
<button onclick="acceptCookies()">Accetta</button>
<button class="reject" onclick="rejectCookies()">Rifiuta</button>
</div>
<script>
const params = new URLSearchParams(window.location.search);
document.getElementById('source-field').value = params.get('source') || 'direct';
function acceptCookies(){{localStorage.setItem('cc','1');document.getElementById('cookie-banner').classList.add('hidden')}}
function rejectCookies(){{localStorage.setItem('cc','0');document.getElementById('cookie-banner').classList.add('hidden')}}
if(localStorage.getItem('cc')!==null){{document.getElementById('cookie-banner').classList.add('hidden')}}
document.getElementById('subscribe-form').addEventListener('submit',async function(e){{
e.preventDefault();
const fd=new FormData(this);
const r=await fetch('/api/subscribe',{{method:'POST',body:JSON.stringify(Object.fromEntries(fd)),headers:{{'Content-Type':'application/json'}}}});
if(r.ok){{window.location.href='thank-you.html'}}else{{alert('Errore. Riprova.')}}
}});
</script>
<noscript><p style="text-align:center;padding:20px">Abilita JavaScript per inviare il modulo. QR: {qr}</p></noscript>
</body>
</html>
"""


def _thank_you_html(title: str, publisher: str) -> str:
    t = escape(title)
    p = escape(publisher)
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Grazie - {t}</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<div class="container">
<h1>Grazie!</h1>
<div class="card">
<p>Controlla la tua casella email — ti abbiamo inviato il link per <strong>confermare l'iscrizione</strong> (double opt-in).</p>
<p>Dopo la conferma riceverai immediatamente il bonus.</p>
<p style="font-size:.9rem;opacity:.7">Se non vedi l'email, controlla la cartella spam.</p>
</div>
<footer>&copy; {p} &middot; <a href="privacy.html">Privacy</a></footer>
</div>
</body>
</html>
"""


def _privacy_html(publisher: str, controller_email: str = "privacy@dailyburnoutpress.com") -> str:
    p = escape(publisher)
    e = escape(controller_email)
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Privacy Policy - {p}</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<div class="container">
<h1>Privacy Policy</h1>
<div class="card">
<h2>Titolare del trattamento</h2>
<p>{p}. Contatto privacy: <a href="mailto:{e}">{e}</a>.</p>
<h2>Dati raccolti</h2>
<p>Indirizzo email, fornito volontariamente tramite il modulo di iscrizione, e fonte (parametro <code>source</code> dell'URL) per finalit&agrave; di analisi interna.</p>
<h2>Finalit&agrave;</h2>
<p>Invio di comunicazioni email a carattere editoriale e promozionale relative ai libri pubblicati da {p}, previo consenso esplicito (art. 6 §1 lett. a GDPR).</p>
<h2>Base giuridica</h2>
<p>Consenso dell'interessato (art. 6 §1 lett. a GDPR), revocabile in qualsiasi momento tramite il link "disiscriviti" presente in ogni email.</p>
<h2>Periodo di conservazione</h2>
<p>I dati sono conservati fino a revoca del consenso. La revoca pu&ograve; essere esercitata in ogni momento.</p>
<h2>Responsabili del trattamento</h2>
<p>Brevo (sendinblue.com) come responsabile esterno per l'invio delle email — dati ospitati nell'UE.</p>
<h2>Diritti dell'interessato</h2>
<p>Ai sensi degli artt. 15-22 GDPR puoi richiedere accesso, rettifica, cancellazione, limitazione, portabilit&agrave; e opposizione scrivendo a <a href="mailto:{e}">{e}</a>.</p>
<h2>Cookie</h2>
<p>Il sito utilizza esclusivamente cookie tecnici (localStorage per memorizzare la scelta sul banner cookie). Nessun cookie di profilazione o tracking di terze parti.</p>
<h2>Reclami</h2>
<p>Hai diritto di proporre reclamo al Garante per la protezione dei dati personali (garanteprivacy.it).</p>
</div>
<footer>&copy; {p}</footer>
</div>
</body>
</html>
"""


def generate_landing_page(
    title: str,
    headline: str,
    primary_color: str = "#1a1a2e",
    accent_color: str = "#e94560",
    dark_mode: bool = True,
    qr_url: str = "",
    publisher: str = "The Daily Burnout Press",
    controller_email: Optional[str] = None,
) -> bytes:
    """Build a 4-file landing bundle and return it as ZIP bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", _index_html(title, headline, qr_url, publisher))
        zf.writestr("thank-you.html", _thank_you_html(title, publisher))
        zf.writestr(
            "privacy.html",
            _privacy_html(publisher, controller_email or "privacy@dailyburnoutpress.com"),
        )
        zf.writestr("style.css", _style_css(primary_color, accent_color, dark_mode))
    return buf.getvalue()


if __name__ == "__main__":
    z = generate_landing_page(
        title="Zodiaco Esaurito",
        headline="12 segni, 30 illustrazioni, zero filtri.",
        qr_url="https://example.com?source=zodiac",
    )
    print(f"Bundle: {len(z)} bytes")
