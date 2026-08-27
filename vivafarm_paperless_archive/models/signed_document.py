"""viva.signed.document extension — Paperless archive linkage.

The archive module is a strict Odoo extension of the sign module's model.
It adds paperless_* fields and the upload FSM. It NEVER changes sign-module
behavior: if this module is uninstalled, signing works exactly as before.
"""
import base64

from odoo import api, fields, models


class SignedDocumentPaperless(models.Model):
    _inherit = 'viva.signed.document'

    paperless_document_id = fields.Integer(
        string='Paperless Document ID', readonly=True, copy=False,
        help='Paperless-ngx document pk (set once upload succeeds).')
    paperless_upload_state = fields.Selection([
        ('none', 'Not Archived'),
        ('pending', 'Pending Upload'),
        ('uploaded', 'Uploaded'),
        ('failed', 'Upload Failed'),
        ('verified', 'Archived & Verified'),
        ('mismatch', 'Archive Mismatch'),
    ], string='Paperless Archive State', default='none', copy=False,
        help='Upload FSM. verified/mismatch are set by verify actions.')
    paperless_upload_error = fields.Text(
        string='Paperless Upload Error', readonly=True, copy=False)
    paperless_title = fields.Char(
        string='Paperless Title', readonly=True, copy=False)
    paperless_uploaded_at = fields.Datetime(
        string='Paperless Uploaded At', readonly=True, copy=False)
    paperless_sha256_of_uploaded = fields.Char(
        string='Paperless Upload SHA-256', readonly=True, copy=False,
        help='SHA-256 of the exact bytes uploaded (self-contained proof; '
             "Paperless's own checksum is MD5 and not security-grade).")
    paperless_last_verified_at = fields.Datetime(
        string='Paperless Last Verified At', readonly=True, copy=False)

    # ── Upload trigger (user decision: AUTO-upload) ──
    def write(self, vals):
        """Flip 'none' -> 'pending' when the signed PDF attachment lands.

        Every seal path in vivafarm_document_sign (SO / DN / tax invoice /
        plain invoice / receipt / manual upload) writes signed_attachment_id
        on an already-signed record — that write is the single seam for
        auto-archive. The transition only fires from 'none', so re-signs,
        verify updates, and the cron's own state writes never re-trigger.
        The upload itself runs in the cron (slice 5) — this never blocks the
        sign flow (Paperless down => the record simply stays 'pending').
        """
        trigger = ('signed_attachment_id' in vals
                   and vals.get('signed_attachment_id')
                   and 'paperless_upload_state' not in vals)
        res = super().write(vals)
        if trigger:
            for rec in self:
                if (rec.paperless_upload_state == 'none'
                        and rec.signed_attachment_id
                        and rec.state == 'signed'):
                    super(SignedDocumentPaperless, rec).write(
                        {'paperless_upload_state': 'pending'})
        return res

    # ── EN-first title (user decision: EN first) ──
    def _paperless_title(self):
        """'<Document Type> - <Number> - <Signer>' (signer omitted when empty)."""
        self.ensure_one()
        type_label = dict(
            self._fields['document_type'].selection).get(
                self.document_type, self.document_type)
        parts = [type_label, self.document_number or '']
        if self.signer_name:
            parts.append(self.signer_name)
        return ' - '.join(p for p in parts if p)

    # ── Config (system parameters; the res.config.settings UI is slice 7) ──
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

    # ── Upload ──
    def _paperless_upload(self):
        """Upload this signed doc to Paperless. Returns True on success.

        Non-blocking by contract: raises on failure (network/HTTP/
        consumption); the CALLER (cron/button) decides how to record it.
        Also ensures the linkage custom fields exist (idempotent).
        """
        self.ensure_one()
        client = self._paperless_client()
        cfg = self._paperless_config()
        pdf_bytes = base64.b64decode(self.signed_attachment_id.datas)

        verify_base = self.env['ir.config_parameter'].sudo().get_param(
            'vivafarm_document_sign.verify_base_url', cfg['base_url'])
        cf_values = {
            'odoo_model': self.odoo_model,
            'odoo_record_id': self.odoo_record_id,
            'odoo_signed_doc_id': self.id,
            'odoo_doc_number': self.document_number or '',
            'odoo_sha256': self.pdf_sha256 or '',
            'odoo_verify_url': '%s/v/%s' % (verify_base,
                                            self.verification_token or ''),
        }
        cf = {}
        # NOTE: data_type enum on Paperless 2.20.15 (v9) uses 'string', NOT
        # 'text' (verified via Django shell 2026-08-27 — 'text' is rejected
        # with HTTP 400 by /api/custom_fields/).
        for name, dtype in (('odoo_model', 'string'),
                            ('odoo_record_id', 'integer'),
                            ('odoo_signed_doc_id', 'integer'),
                            ('odoo_doc_number', 'string'),
                            ('odoo_sha256', 'string'),
                            ('odoo_verify_url', 'url')):
            cf[client.ensure_custom_field(name, dtype)] = cf_values[name]

        # Search-first adoption (design §5): Paperless does NOT reject
        # duplicates by default, so a retry after a mid-upload blip would
        # create a second copy. If a doc for this signed record already
        # exists, adopt its id instead of uploading again.
        existing = client.search_by_custom_field('odoo_signed_doc_id', self.id)
        if existing:
            doc_id = existing[0]
        else:
            doc_id, _task_id = client.upload_pdf(
                title=self._paperless_title(),
                pdf_bytes=pdf_bytes,
                custom_fields=cf,
                document_type_id=cfg['document_type_id'] or None,
                tag_ids=[cfg['tag_id']] if cfg['tag_id'] else None,
            )
        self.write({
            'paperless_document_id': doc_id,
            'paperless_upload_state': 'uploaded',
            'paperless_title': self._paperless_title(),
            'paperless_uploaded_at': fields.Datetime.now(),
            'paperless_sha256_of_uploaded': client.sha256(pdf_bytes),
            'paperless_upload_error': False,
        })
        self._log_event('HASHED',
                        detail='paperless_upload doc_id=%s' % doc_id)
        return True

    # ── Verify (download back + semantic check) ──
    def _paperless_verify(self):
        """Download the archived copy and check it is intact.

        Paperless rewrites born-digital PDFs during OCR, so byte-identity is
        impossible by design. The semantic check: the archive copy is a valid
        PDF AND its extracted text contains this document's own number
        (e.g. 'INV/2026/00055'). Raises on network failure; returns False
        (and sets 'mismatch') when the copy is invalid/unreadable.
        """
        self.ensure_one()
        if not self.paperless_document_id:
            raise ValueError('no paperless_document_id to verify')
        client = self._paperless_client()
        data = client.download_document(self.paperless_document_id)
        ok_pdf = data[:5] == b'%PDF-'
        from io import BytesIO
        from pypdf import PdfReader
        text = ''
        try:
            text = ''.join(p.extract_text() or ''
                           for p in PdfReader(BytesIO(data)).pages)
        except Exception:
            text = ''
        if ok_pdf and self.document_number and self.document_number in text:
            self.write({
                'paperless_upload_state': 'verified',
                'paperless_last_verified_at': fields.Datetime.now(),
                'paperless_upload_error': False,
            })
            self._log_event('VERIFIED', detail='paperless_verify ok')
            return True
        self.write({
            'paperless_upload_state': 'mismatch',
            'paperless_upload_error': (
                'archived copy invalid or missing document number '
                '(pdf=%s, num_in_text=%s)' % (ok_pdf,
                                              self.document_number in text)),
        })
        self._log_event('VERIFIED', detail='paperless_verify MISMATCH')
        return False

    # ── Cron entry points (never raise — a failing upload must not kill
    #    the whole cron tick) ──
    @api.model
    def _cron_process_pending_uploads(self, limit=50):
        """Upload every pending/failed signed doc (auto-upload + retry)."""
        records = self.sudo().search([
            ('paperless_upload_state', 'in', ('pending', 'failed')),
            ('signed_attachment_id', '!=', False),
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
        """Re-verify archived copies (scheduled verify option)."""
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

    # ── On-demand + batch verify (user decision) ──
    def action_paperless_verify(self):
        """On-demand verify for the selected records (form/action button)."""
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

    @api.model
    def _paperless_verify_batch(self, limit=100):
        """Batch verify ALL uploaded/verified records (server action)."""
        records = self.sudo().search([
            ('paperless_upload_state', 'in', ('uploaded', 'verified')),
        ], limit=limit)
        ok = bad = skipped = 0
        for rec in records:
            if not rec.paperless_document_id:
                skipped += 1
                continue
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
        return (ok, bad, skipped)

    # ── Backfill (records signed before the archive module existed) ──
    @api.model
    def _paperless_backfill(self, limit=200):
        """Archive signed docs that predate the module (state 'none').

        The upload trigger only fires on NEW writes of signed_attachment_id;
        records signed before this module was installed sit in 'none'
        forever. This flips them to 'pending' so the upload cron picks them
        up. Idempotent: skips records that already have a Paperless doc id.
        """
        records = self.sudo().search([
            ('paperless_upload_state', '=', 'none'),
            ('signed_attachment_id', '!=', False),
            ('state', '=', 'signed'),
        ], limit=limit)
        for rec in records:
            if rec.paperless_document_id:
                continue
            rec.write({'paperless_upload_state': 'pending'})
        return len(records)
