#!/usr/bin/env bash
# One-time Paperless workflow setup for the Odoo webhook (Paperless -> Odoo).
#
# Creates the "Odoo Webhook Notify" workflow: trigger "Document Added"
# (sources: consumption folder, API, mail) -> action "Webhook" POSTing a
# JSON body to the Odoo endpoint. Idempotent: skips if the workflow
# already exists.
#
# Prereqs:
#   - The Odoo VM must be reachable from the Paperless VM by hostname
#     (add "10.10.10.11 <db>.stg.vivafarm" to /etc/hosts on Paperless —
#     Paperless's webhook transport FORCES the Host header to the URL's
#     hostname, and Odoo's dbfilter routes by hostname).
#   - PAPERLESS_URL + PAPERLESS_TOKEN (API token).
#
# Usage:
#   PAPERLESS_URL=http://10.10.10.15:8000 PAPERLESS_TOKEN=<token> \
#       ODOO_WEBHOOK_URL=http://test_sign.stg.vivafarm:8069/paperless/webhook \
#       ./paperless_webhook_setup.sh
#
# NOTE: Paperless 2.20.15 has NO {{doc_id}} placeholder — the doc id rides
# inside {{doc_url}} (/documents/<id>/); the Odoo controller extracts it.
set -euo pipefail

URL="${PAPERLESS_URL:-http://10.10.10.15:8000}"
TOKEN="${PAPERLESS_TOKEN:?PAPERLESS_TOKEN is required}"
WEBHOOK_URL="${ODOO_WEBHOOK_URL:?ODOO_WEBHOOK_URL is required}"
AUTH="Authorization: Token ${TOKEN}"

echo "==> Paperless: $URL"
echo "==> Webhook target: $WEBHOOK_URL"

# ── Idempotency: skip if the workflow already exists ──
existing=$(curl -sf -H "$AUTH" "$URL/api/workflows/" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for w in data.get('results', []):
    if w['name'] == 'Odoo Webhook Notify':
        print(w['id']); break
")
if [ -n "$existing" ]; then
    echo "==> Workflow 'Odoo Webhook Notify' already exists (id=$existing) — nothing to do."
    exit 0
fi

# ── Create the workflow ──
# Trigger type 2 = Document Added; sources 1,2,3 = consumption folder,
# API, mail. Action type 4 = Webhook. as_json=true sends the rendered
# body as a JSON-encoded string (the Odoo controller handles both shapes).
BODY='{"title": "{{doc_title}}", "url": "{{doc_url}}", "original_filename": "{{original_filename}}", "document_type": "{{document_type}}", "correspondent": "{{correspondent}}", "created": "{{created}}"}'
PAYLOAD=$(python3 -c "
import json, sys
body = '''$BODY'''
workflow = {
    'name': 'Odoo Webhook Notify',
    'order': 1,
    'enabled': True,
    'triggers': [{'type': 2, 'sources': [1, 2, 3]}],
    'actions': [{'type': 4, 'webhook': {
        'url': '$WEBHOOK_URL',
        'as_json': True,
        'use_params': False,
        'body': body,
        'headers': {},
    }}],
}
print(json.dumps(workflow))
")
resp=$(curl -sf -X POST -H "$AUTH" -H 'Content-Type: application/json' \
    -d "$PAYLOAD" "$URL/api/workflows/")
wid=$(echo "$resp" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "==> Created workflow 'Odoo Webhook Notify' (id=$wid)"
echo "==> DONE. New documents consumed in Paperless now POST to $WEBHOOK_URL"
