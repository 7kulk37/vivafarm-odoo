"""paperless.document — archive ANY file (scanned/photographed papers,
receipts, contracts, GAP sheets) into Paperless-ngx.

Same decoupled pattern as the signed-doc extension: upload runs in the
cron, failures land in 'failed' with the error text, retry is automatic.
The record links to any Odoo record via model_id + res_id (the standard
Odoo generic-link pattern, same as mail.attachment).
"""
import base64
import hashlib

from odoo import api, fields, models


class PaperlessDocument(models.Model):
    _name = 'paperless.document'
    _description = 'Paperless Archived Document'
    _order = 'create_date desc'

    name = fields.Char(string='Title', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
    model_id = fields.Many2one('ir.model', string='Linked Model',
                               help='Odoo model the document belongs to '
                                    '(e.g. sale.order, account.move).')
    res_id = fields.Integer(string='Record ID',
                            help='Odoo record id within the linked model.')
    document_date = fields.Date(string='Document Date')
    source_filename = fields.Char(string='Source Filename')
    file = fields.Binary(string='File', attachment=True, required=True)
    note = fields.Text(string='Note')

    # ── Paperless linkage (same FSM as viva.signed.document) ──
    paperless_document_id = fields.Integer(
        string='Paperless Document ID', readonly=True, copy=False)
    paperless_upload_state = fields.Selection([
        ('none', 'Not Archived'),
        ('pending', 'Pending Upload'),
        ('uploaded', 'Uploaded'),
        ('failed', 'Upload Failed'),
        ('verified', 'Archived & Verified'),
        ('mismatch', 'Archive Mismatch'),
    ], string='Paperless Archive State', default='none', copy=False)
    paperless_upload_error = fields.Text(
        string='Paperless Upload Error', readonly=True, copy=False)
    paperless_title = fields.Char(
        string='Paperless Title', readonly=True, copy=False)
    paperless_uploaded_at = fields.Datetime(
        string='Paperless Uploaded At', readonly=True, copy=False)
    paperless_sha256_of_uploaded = fields.Char(
        string='Paperless Upload SHA-256', readonly=True, copy=False)
    paperless_last_verified_at = fields.Datetime(
        string='Paperless Last Verified At', readonly=True, copy=False)

    # ── Upload trigger: file lands -> pending ──
    def write(self, vals):
        trigger = ('file' in vals and vals.get('file')
                   and 'paperless_upload_state' not in vals)
        res = super().write(vals)
        if trigger:
            for rec in self:
                if rec.paperless_upload_state == 'none' and rec.file:
                    super(PaperlessDocument, rec).write(
                        {'paperless_upload_state': 'pending'})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.file and rec.paperless_upload_state == 'none':
                rec.write({'paperless_upload_state': 'pending'})
        return records

    # ── Config + client (shared with the signed-doc extension) ──
    @api.model
    def _paperless_config(self):
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'base_url': ICP.get_param('vivafarm_paperless_archive.base_url',
                                      'http://10.10.10.15:8000'),
            'token': ICP.get_param('vivafarm_paperless_archive.token', ''),
            'document_type_id': int(ICP.get_param(
                'vivafarm_paperless_archive.document_type_id', '0') or 0),
            'tag_id': int(ICP.get_param(
                'vivafarm_paperless_archive.tag_id', '0') or 0),
        }

    def _paperless_client(self):
        from odoo.addons.vivafarm_paperless_archive.services.paperless_client import (
            PaperlessClient,
        )
        cfg = self._paperless_config()
        return PaperlessClient(cfg['base_url'], cfg['token'])

    def _paperless_title(self):
        self.ensure_one()
        return self.name or self.source_filename or 'Document'

    def _paperless_upload(self):
        """Upload this file to Paperless. Returns True on success."""
        self.ensure_one()
        client = self._paperless_client()
        cfg = self._paperless_config()
        file_bytes = base64.b64decode(self.file)

        cf_values = {
            'odoo_model': self.model_id.model if self.model_id else '',
            'odoo_record_id': self.res_id or 0,
            'odoo_doc_id': self.id,
            'odoo_doc_number': self.name or '',
            'odoo_sha256': hashlib.sha256(file_bytes).hexdigest(),
        }
        cf = {}
        for name, dtype in (('odoo_model', 'string'),
                            ('odoo_record_id', 'integer'),
                            ('odoo_doc_id', 'integer'),
                            ('odoo_doc_number', 'string'),
                            ('odoo_sha256', 'string')):
            cf[client.ensure_custom_field(name, dtype)] = cf_values[name]

        # Search-first adoption keyed on the record's OWN id (the name is
        # user-entered and not unique — two docs can share a title).
        existing = client.search_by_custom_field('odoo_doc_id', self.id)
        if existing:
            doc_id = existing[0]
        else:
            doc_id, _task_id = client.upload_pdf(
                title=self._paperless_title(),
                pdf_bytes=file_bytes,
                custom_fields=cf,
                document_type_id=cfg['document_type_id'] or None,
                tag_ids=[cfg['tag_id']] if cfg['tag_id'] else None,
                created=self.document_date and self.document_date.isoformat(),
            )
        self.write({
            'paperless_document_id': doc_id,
            'paperless_upload_state': 'uploaded',
            'paperless_title': self._paperless_title(),
            'paperless_uploaded_at': fields.Datetime.now(),
            'paperless_sha256_of_uploaded': client.sha256(file_bytes),
            'paperless_upload_error': False,
        })
        return True

    def _paperless_verify(self):
        """Download back + semantic check (PDF: valid + title in text;
        image: non-empty download)."""
        self.ensure_one()
        if not self.paperless_document_id:
            raise ValueError('no paperless_document_id to verify')
        client = self._paperless_client()
        data = client.download_document(self.paperless_document_id)
        ok_pdf = data[:5] == b'%PDF-'
        if ok_pdf:
            from io import BytesIO
            from pypdf import PdfReader
            text = ''
            try:
                text = ''.join(p.extract_text() or ''
                               for p in PdfReader(BytesIO(data)).pages)
            except Exception:
                text = ''
            ok = bool(self.name) and self.name in text
        else:
            # Image archive copy: Paperless converts to PDF, so a non-PDF
            # download is suspicious; require non-empty at minimum.
            ok = len(data) > 0
        if ok:
            self.write({
                'paperless_upload_state': 'verified',
                'paperless_last_verified_at': fields.Datetime.now(),
                'paperless_upload_error': False,
            })
            return True
        self.write({
            'paperless_upload_state': 'mismatch',
            'paperless_upload_error': (
                'archived copy invalid (pdf=%s, title_in_text=%s)'
                % (ok_pdf, ok)),
        })
        return False

    # ── Cron entry points ──
    @api.model
    def _cron_process_pending_uploads(self, limit=50):
        records = self.sudo().search([
            ('paperless_upload_state', 'in', ('pending', 'failed')),
            ('file', '!=', False),
        ], limit=limit)
        done = failed = 0
        for rec in records:
            try:
                rec._paperless_upload()
                done += 1
            except Exception as e:
                rec.write({
                    'paperless_upload_state': 'failed',
                    'paperless_upload_error': str(e)[:500],
                })
                failed += 1
        return (done, failed)

    @api.model
    def _cron_verify_archived(self, limit=50):
        records = self.sudo().search([
            ('paperless_upload_state', 'in', ('uploaded', 'verified')),
        ], limit=limit)
        ok = bad = 0
        for rec in records:
            try:
                if rec._paperless_verify():
                    ok += 1
                else:
                    bad += 1
            except Exception as e:
                rec.write({
                    'paperless_upload_state': 'mismatch',
                    'paperless_upload_error': str(e)[:500],
                })
                bad += 1
        return (ok, bad)

    def action_paperless_verify(self):
        for rec in self:
            if not rec.paperless_document_id:
                continue
            try:
                rec._paperless_verify()
            except Exception as e:
                rec.write({
                    'paperless_upload_state': 'mismatch',
                    'paperless_upload_error': str(e)[:500],
                })
        return True
