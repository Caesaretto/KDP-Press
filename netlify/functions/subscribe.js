// Netlify Function — Brevo opt-in endpoint with hardening.
// Env vars (Netlify dashboard → Site settings → Env vars):
//   BREVO_API_KEY    — Brevo API key
//   BREVO_LIST_ID    — Brevo list ID (integer)
//   ALLOWED_ORIGIN   — comma-separated origin allow-list (e.g. "https://thedailyburnoutpress.com,https://www.thedailyburnoutpress.com")

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[a-zA-Z]{2,}$/;
const RATE_LIMIT_WINDOW_MS = 60_000; // 1 min
const RATE_LIMIT_MAX = 5;            // max 5 requests per IP per minute
const _rate = new Map();             // ip -> [timestamps]

function clientIp(event) {
  const xff = event.headers["x-forwarded-for"] || event.headers["X-Forwarded-For"];
  if (xff) return xff.split(",")[0].trim();
  return event.headers["client-ip"] || "unknown";
}

function isRateLimited(ip) {
  const now = Date.now();
  const arr = (_rate.get(ip) || []).filter(t => now - t < RATE_LIMIT_WINDOW_MS);
  if (arr.length >= RATE_LIMIT_MAX) {
    _rate.set(ip, arr);
    return true;
  }
  arr.push(now);
  _rate.set(ip, arr);
  return false;
}

function corsHeaders(origin) {
  const allowed = (process.env.ALLOWED_ORIGIN || "").split(",").map(s => s.trim()).filter(Boolean);
  if (allowed.length && origin && allowed.includes(origin)) {
    return {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Vary": "Origin",
    };
  }
  return {};
}

export async function handler(event) {
  const origin = event.headers.origin || event.headers.Origin || "";
  const cors = corsHeaders(origin);

  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers: cors, body: "" };
  }
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, headers: cors, body: "Method Not Allowed" };
  }

  // CORS allow-list enforcement when configured
  if (process.env.ALLOWED_ORIGIN && !cors["Access-Control-Allow-Origin"]) {
    return { statusCode: 403, body: "Origin not allowed" };
  }

  const ip = clientIp(event);
  if (isRateLimited(ip)) {
    return { statusCode: 429, headers: cors, body: "Too Many Requests" };
  }

  let email, source, honeypot;
  try {
    ({ email, source, honeypot } = JSON.parse(event.body || "{}"));
  } catch {
    return { statusCode: 400, headers: cors, body: "Invalid JSON" };
  }

  // Honeypot field: bots tend to fill every input
  if (honeypot) {
    return {
      statusCode: 200,
      headers: { ...cors, "Content-Type": "application/json" },
      body: JSON.stringify({ success: true }),
    };
  }

  if (typeof email !== "string" || email.length > 254 || !EMAIL_RE.test(email)) {
    return { statusCode: 400, headers: cors, body: "Invalid email" };
  }
  if (source && (typeof source !== "string" || source.length > 64)) {
    return { statusCode: 400, headers: cors, body: "Invalid source" };
  }

  const apiKey = process.env.BREVO_API_KEY;
  const listId = parseInt(process.env.BREVO_LIST_ID || "1", 10);

  if (!apiKey) {
    console.error("BREVO_API_KEY not set");
    return { statusCode: 500, headers: cors, body: "Server configuration error" };
  }

  const res = await fetch("https://api.brevo.com/v3/contacts", {
    method: "POST",
    headers: {
      "api-key": apiKey,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      email,
      listIds: [listId],
      updateEnabled: true,
      attributes: {
        SOURCE: source || "kdp_book_qr",
        BOOK: "zodiaco_esaurito",
      },
    }),
  });

  if (res.ok || res.status === 204) {
    return {
      statusCode: 200,
      headers: { ...cors, "Content-Type": "application/json" },
      body: JSON.stringify({ success: true }),
    };
  }

  const err = await res.json().catch(() => ({}));
  console.error("Brevo error:", res.status, err);
  return {
    statusCode: res.status,
    headers: cors,
    body: JSON.stringify({ error: err.message || "Brevo API error" }),
  };
}
