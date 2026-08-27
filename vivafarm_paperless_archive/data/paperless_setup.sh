#!/usr/bin/env bash
# One-time Paperless-ngx setup for vivafarm_paperless_archive.
#
# Creates the document type + tag the module expects, idempotently.
# Custom fields (odoo_model, odoo_record_id, odoo_signed_doc_id,
# odoo_doc_number, odoo_sha256, odoo_verify_url) are auto-created by the
# module on first upload — this script only handles type + tag.
#
# Usage:
#   PAPERLESS_URL=http://10.10.10.15:8000 PAPERLESS_TOKEN=<token> \
#       ./paperless_setup.sh
#
# Prints the document_type_id and tag_id to paste into
# Settings > General > Paperless Archive.
set -euo pipefail

URL="${PAPERLESS_URL:-http://10.10.10.15:8000}"
TOKEN="${PAPERLESS_TOKEN:?PAPERLESS_TOKEN is required}"
AUTH="Authorization: Token ${TOKEN}"
DOC_TYPE_NAME="Odoo Signed Document"
TAG_NAME="odoo-archived"

api_get() { curl -sf -H "$AUTH" "$URL$1"; }
api_post() { curl -sf -H "$AUTH" -H 'Content-Type: application/json' -d "$2" "$URL$1"; }

echo "==> Paperless: $URL"

# ── Document type ──
existing_type=$(api_get /api/document_types/ | python3 -c "
import json,sys
data=json.load(sys.stdin)
for t in data.get('results', []):
    if t['name'] == '$DOC_TYPE_NAME':
        print(t['id']); break
")
if [ -n "$existing_type" ]; then
    echo "==> Document type '$DOC_TYPE_NAME' already exists (id=$existing_type)"
    DOC_TYPE_ID=$existing_type
else
    DOC_TYPE_ID=$(api_post /api/document_types/ "{\"name\": \"$DOC_TYPE_NAME\"}" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
    echo "==> Created document type '$DOC_TYPE_NAME' (id=$DOC_TYPE_ID)"
fi

# ── Tag ──
existing_tag=$(api_get /api/tags/ | python3 -c "
import json,sys
data=json.load(sys.stdin)
for t in data.get('results', []):
    if t['name'] == '$TAG_NAME':
        print(t['id']); break
")
if [ -n "$existing_tag" ]; then
    echo "==> Tag '$TAG_NAME' already exists (id=$existing_tag)"
    TAG_ID=$existing_tag
else
    TAG_ID=$(api_post /api/tags/ "{\"name\": \"$TAG_NAME\"}" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
    echo "==> Created tag '$TAG_NAME' (id=$TAG_ID)"
fi

echo
echo "==> DONE. Set these in Odoo Settings > General > Paperless Archive:"
echo "    Document Type ID: $DOC_TYPE_ID"
echo "    Tag ID:           $TAG_ID"
