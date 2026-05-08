// Netlify Function — aggiunge il contatto alla lista Brevo
// Variabili d'ambiente necessarie (Netlify dashboard → Site settings → Env vars):
//   BREVO_API_KEY   → la tua API key di Brevo
//   BREVO_LIST_ID   → l'ID della lista Brevo (numero intero)

export async function handler(event) {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  let email, source;
  try {
    ({ email, source } = JSON.parse(event.body));
  } catch {
    return { statusCode: 400, body: "Invalid JSON" };
  }

  if (!email || !email.includes("@")) {
    return { statusCode: 400, body: "Invalid email" };
  }

  const apiKey = process.env.BREVO_API_KEY;
  const listId = parseInt(process.env.BREVO_LIST_ID || "1", 10);

  if (!apiKey) {
    console.error("BREVO_API_KEY not set");
    return { statusCode: 500, body: "Server configuration error" };
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

  // 204 = contact already exists, still a success
  if (res.ok || res.status === 204) {
    return {
      statusCode: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ success: true }),
    };
  }

  const err = await res.json().catch(() => ({}));
  console.error("Brevo error:", res.status, err);
  return {
    statusCode: res.status,
    body: JSON.stringify({ error: err.message || "Brevo API error" }),
  };
}
