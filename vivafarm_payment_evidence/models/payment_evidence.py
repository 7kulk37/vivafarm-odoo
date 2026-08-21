from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

import base64
import re


class PaymentEvidence(models.Model):
    _name = 'viva.payment.evidence'
    _description = 'Customer payment evidence upload'
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, readonly=True)
    transaction_id = fields.Many2one('payment.transaction', string='Transaction', readonly=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    state = fields.Selection([
        ('pending', 'Pending Review'),
        ('validated', 'Validated'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending', required=True)
    filename = fields.Char(string='File Name', readonly=True)
    mimetype = fields.Char(string='File Type', readonly=True)
    file_size = fields.Integer(string='File Size (bytes)', readonly=True)
    attachment_id = fields.Many2one('ir.attachment', string='File', readonly=True, ondelete='restrict')
    check_result = fields.Text(string='Check Result', readonly=True)
    validated_by = fields.Many2one('res.users', string='Validated By', readonly=True)
    validated_at = fields.Datetime(string='Validated At', readonly=True)

    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Evidence reference must be unique.'),
    ]

    @api.model
    def _default_currency(self):
        return self.env.company.currency_id

    def action_validate(self):
        for rec in self:
            rec.write({
                'state': 'validated',
                'validated_by': self.env.user.id,
                'validated_at': fields.Datetime.now(),
            })

    def action_reject(self):
        for rec in self:
            rec.write({
                'state': 'rejected',
                'validated_by': self.env.user.id,
                'validated_at': fields.Datetime.now(),
            })


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    evidence_ids = fields.One2many('viva.payment.evidence', 'transaction_id', string='Payment Evidence')
    evidence_count = fields.Integer(compute='_compute_evidence_count', string='Evidence Count')

    @api.depends('evidence_ids')
    def _compute_evidence_count(self):
        for tx in self:
            tx.evidence_count = len(tx.evidence_ids)

    def _get_manual_signed_document(self):
        """The manual hand-signed payment slip sealed for this tx, if any.

        Defensive KeyError: viva.signed.document may not be in the registry
        during payment_evidence's own load-time template render-check.
        """
        try:
            model = self.env['viva.signed.document']
        except KeyError:
            return None
        return model.sudo().search([
            ('payment_id', '=', self.payment_id.id),
            ('document_type', '=', 'payment_slip'),
            ('channel', '=', 'manual'),
        ], limit=1)

    def action_view_evidence(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payment Evidence',
            'res_model': 'viva.payment.evidence',
            'view_mode': 'list,form',
            'domain': [('transaction_id', '=', self.id)],
            'context': {'default_transaction_id': self.id},
        }


class PaymentEvidenceCheck(models.AbstractModel):
    """Basic check that an uploaded file looks like a real paid transaction."""

    _name = 'viva.payment.evidence.check'
    _description = 'Basic paid-transaction check for uploaded evidence'

    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_MIMETYPES = {
        'application/pdf': 'pdf',
        'image/png': 'png',
        'image/jpeg': 'jpg',
    }

    @api.model
    def _check(self, tx, filename, mimetype, data):
        """Return (state, message). state: 'validated' | 'pending'."""
        if mimetype not in self.ALLOWED_MIMETYPES:
            return 'pending', 'Unsupported file type: %s' % mimetype
        if len(data) > self.MAX_SIZE:
            return 'pending', 'File too large (max 10 MB)'

        text = ''
        if mimetype == 'application/pdf':
            text = self._extract_pdf_text(data)

        if not text:
            return 'pending', 'No readable text in file — manual review required'

        ref = tx.reference or ''
        # The customer's bank slip carries the invoice number, not the
        # transaction reference with its suffix (INV/2026/00009-8). Match
        # both the full reference and the base reference.
        base_ref = re.sub(r'-\d+$', '', ref)
        refs = {r for r in (ref, base_ref) if r}
        amount = tx.amount or 0.0
        ref_hit = any(r in text for r in refs)
        amount_hit = self._amount_in_text(amount, text)
        if ref_hit and amount_hit:
            return 'validated', 'Reference and amount matched in PDF text'
        if ref_hit:
            return 'pending', 'Reference matched but amount not found — manual review'
        if amount_hit:
            return 'pending', 'Amount matched but reference not found — manual review'
        return 'pending', 'No reference or amount found in text — manual review'

    @api.model
    def _extract_pdf_text(self, data):
        import subprocess
        import tempfile
        import os
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(data)
                path = f.name
            try:
                out = subprocess.run(
                    ['pdftotext', path, '-'],
                    capture_output=True, timeout=30,
                )
                return out.stdout.decode('utf-8', errors='replace')
            finally:
                os.unlink(path)
        except Exception:
            return ''

    @api.model
    def _amount_in_text(self, amount, text):
        """Match the amount as it appears in Thai bank slips: 1,200.00 / 1200.00 / ฿1,200."""
        if not amount:
            return False
        # Normalize: strip spaces, unify commas/dots
        norm = re.sub(r'\s+', '', text)
        # Try the amount with 2 decimals and without
        for fmt in ('%0.2f', '%0.0f'):
            s = fmt % amount
            if s in norm:
                return True
            # With thousands separator
            s_sep = re.sub(r'(\d)(?=(\d{3})+(?!\d))', r'\1,', s)
            if s_sep in norm:
                return True
        return False
