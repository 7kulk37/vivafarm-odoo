"""paperless.incoming.event — append-only log of Paperless webhook receipts.

The Paperless→Odoo direction: a Paperless workflow action (trigger
"Document Added") POSTs a webhook when a document lands in Paperless
(e.g. a scanned GAP sheet). This model records the receipt so Odoo
"knows" the document exists. Append-only by design (no unlink in the
access rules); the webhook is idempotent — a duplicate doc_id is skipped.
"""
from odoo import api, fields, models


class PaperlessIncomingEvent(models.Model):
    _name = 'paperless.incoming.event'
    _description = 'Paperless Incoming Event'
    _order = 'received_at desc'

    paperless_document_id = fields.Integer(
        string='Paperless Document ID', readonly=True)
    title = fields.Char(string='Title', readonly=True)
    url = fields.Char(string='URL', readonly=True)
    source_filename = fields.Char(string='Source Filename', readonly=True)
    document_type = fields.Char(string='Document Type', readonly=True)
    correspondent = fields.Char(string='Correspondent', readonly=True)
    created = fields.Char(string='Created', readonly=True)
    received_at = fields.Datetime(
        string='Received At', readonly=True, default=fields.Datetime.now)
    payload = fields.Text(string='Raw Payload', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        # Idempotency: skip if this Paperless doc was already received.
        for vals in vals_list:
            doc_id = vals.get('paperless_document_id')
            if doc_id and self.search_count(
                    [('paperless_document_id', '=', doc_id)]):
                vals['_skip'] = True
        records = self.browse()
        for vals in vals_list:
            if vals.pop('_skip', False):
                continue
            records |= super().create([vals])
        return records
