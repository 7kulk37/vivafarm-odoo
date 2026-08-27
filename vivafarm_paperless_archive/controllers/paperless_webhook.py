"""Paperless webhook receiver — POST /paperless/webhook.

The Paperless→Odoo direction. A Paperless workflow action (trigger
"Document Added", action "Webhook") POSTs here when a document lands in
Paperless. The workflow must send a JSON body with the placeholders the
module expects (see data/paperless_webhook_setup.sh for the exact
template) and a Host header matching the Odoo DB (dbfilter routes by
hostname).

Security: auth='public' + csrf=False (Paperless has no Odoo session).
The endpoint only APPENDS to paperless.incoming.event — it cannot read
or write business records, so a spoofed POST is harmless noise.
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PaperlessWebhookController(http.Controller):

    @http.route('/paperless/webhook', type='http', auth='public',
                website=False, csrf=False, methods=['POST'])
    def webhook(self, **kwargs):
        raw = request.httprequest.get_data(as_text=True)
        payload = {}
        try:
            payload = json.loads(raw or '{}')
        except ValueError:
            _logger.warning('paperless webhook: non-JSON body: %s',
                            raw[:300])
        # Paperless as_json=true sends the rendered body as a JSON-encoded
        # STRING (json.dumps of the body text) — parse the inner object.
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError:
                _logger.warning('paperless webhook: non-JSON inner body: %s',
                                payload[:300])
        if not isinstance(payload, dict):
            payload = {}

        # Paperless 2.20.15 has no {{doc_id}} placeholder — the doc id rides
        # inside {{doc_url}} (/documents/<id>/). Extract it when absent.
        doc_id = payload.get('doc_id')
        if not doc_id and payload.get('url'):
            import re
            m = re.search(r'/documents/(\d+)/', payload['url'])
            if m:
                doc_id = int(m.group(1))

        vals = {
            'paperless_document_id': doc_id,
            'title': payload.get('title') or payload.get('doc_title'),
            'url': payload.get('url') or payload.get('doc_url'),
            'source_filename': payload.get('original_filename'),
            'document_type': payload.get('document_type'),
            'correspondent': payload.get('correspondent'),
            'created': payload.get('created'),
            'payload': raw[:2000],
        }
        try:
            request.env['paperless.incoming.event'].sudo().create(vals)
        except Exception as e:
            _logger.error('paperless webhook: create failed: %s', e)
            return http.Response('error', status=500)
        return http.Response('ok', status=200)
