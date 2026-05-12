#!/usr/bin/env bash
# Deploy landing/ + netlify/functions/ to Netlify production.
#
# Prereqs (one-time setup):
#   npm install -g netlify-cli
#   netlify login                  # opens a browser to authenticate
#
# First run: this script calls `netlify init` interactively to link the repo
# to a new or existing Netlify site. Subsequent runs go straight to deploy.
#
# Required env vars on the Netlify site (set via `netlify env:set NAME value`):
#   BREVO_API_KEY    Brevo API key for the /api/subscribe function
#   BREVO_LIST_ID    Brevo list id (integer)
#   ALLOWED_ORIGIN   CORS allow-list, comma-separated (e.g. https://thedailyburnoutpress.com)

set -euo pipefail

cd "$(dirname "$0")"

if ! command -v netlify >/dev/null 2>&1; then
  echo "ERROR: 'netlify' CLI not found. Install with: npm install -g netlify-cli" >&2
  exit 1
fi

if [[ ! -f .netlify/state.json ]]; then
  echo "==> Project not linked to a Netlify site yet. Running netlify init…"
  netlify init
fi

echo "==> Checking required env vars on the site…"
missing=0
for V in BREVO_API_KEY BREVO_LIST_ID ALLOWED_ORIGIN; do
  if ! netlify env:list 2>/dev/null | grep -qE "^\s*$V\b"; then
    echo "    ⚠  $V is NOT set on the Netlify site. Set it with: netlify env:set $V <value>" >&2
    missing=1
  fi
done
if [[ $missing -eq 1 ]]; then
  echo "==> Continuing anyway, but /api/subscribe will return 500 until vars are set."
fi

echo "==> Deploying to production…"
netlify deploy --prod --dir=landing --functions=netlify/functions

cat <<'EOF'

==> Done.

Smoke-test the API endpoint:
  curl -i -X POST "https://<your-site>/api/subscribe" \
       -H 'Content-Type: application/json' \
       -d '{"email":"test@example.com","source":"smoke"}'

Expected: HTTP 200 with {"success":true}.
EOF
