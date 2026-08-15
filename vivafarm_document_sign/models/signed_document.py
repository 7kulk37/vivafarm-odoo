"""viva.signed.document — integrity record for a signed tax invoice.

One record per signed invoice. Stores the cryptographic evidence:
document hash, detached RSA signature, certificate metadata, revision
chain, and the verification token used by the public /v/<token> page.

Migration-ready: certificate fields are generic (type/issuer/serial/
fingerprint), so swapping the TEST self-signed cert for a Thai CA cert
is a config/trust change, not a schema change.
"""
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.signing_service import SigningService, sha256_hex


class VivaSignedDocument(models.Model):
    _name = 'viva.signed.document'
    _description = 'Signed Document (Tax Invoice integrity record)'
    _order = 'signed_at desc, id desc'

    # ── Document identity ──
    document_uuid = fields.Char(string='Document UUID', readonly=True, copy=False)
    document_type = fields.Selection([
        ('tax_invoice', 'Tax Invoice'),
    ], string='Document Type', required=True, default='tax_invoice')
    document_number = fields.Char(string='Document Number', readonly=True, copy=False)
    odoo_model = fields.Char(string='Odoo Model', readonly=True, default='account.move')
    odoo_record_id = fields.Integer(string='Odoo Record ID', readonly=True, index=True)
    move_id = fields.Many2one('account.move', string='Invoice', ondelete='restrict', index=True)

    # ── Revision chain (tamper-evident: Rev N hashes back to Rev N-1) ──
    revision = fields.Integer(string='Revision', readonly=True, default=1, copy=False)
    previous_document_hash = fields.Char(string='Previous Document Hash', readonly=True, copy=False)

    # ── State ──
    state = fields.Selection([
        ('signed', 'Signed'),
        ('revoked', 'Revoked'),
    ], string='State', default='signed', readonly=True, copy=False)

    # ── Cryptographic evidence ──
    pdf_sha256 = fields.Char(string='PDF SHA-256', readonly=True, copy=False)
    signature_algorithm = fields.Char(string='Signature Algorithm', readonly=True,
                                      default='RSA-SHA256 (detached)', copy=False)
    signature_b64 = fields.Text(string='Signature (base64)', readonly=True, copy=False)
    public_key_pem = fields.Text(string='Public Key (PEM)', readonly=True, copy=False)

    # ── Certificate metadata (generic names — production CA swap is data-only) ──
    certificate_type = fields.Selection([
        ('TEST', 'TEST / NON-PRODUCTION'),
        ('PRODUCTION', 'PRODUCTION'),
    ], string='Certificate Type', readonly=True, default='TEST', copy=False)
    certificate_subject = fields.Char(string='Certificate Subject', readonly=True, copy=False)
    certificate_issuer = fields.Char(string='Certificate Issuer', readonly=True, copy=False)
    certificate_serial = fields.Char(string='Certificate Serial', readonly=True, copy=False)
    certificate_fingerprint = fields.Char(string='Certificate Fingerprint', readonly=True, copy=False)
    certificate_valid_from = fields.Datetime(string='Certificate Valid From', readonly=True, copy=False)
    certificate_valid_to = fields.Datetime(string='Certificate Valid To', readonly=True, copy=False)

    # ── Signer + time ──
    signer_user_id = fields.Many2one('res.users', string='Signed By', readonly=True)
    signed_at = fields.Datetime(string='Signed At', readonly=True, copy=False)
    revoked_at = fields.Datetime(string='Revoked At', readonly=True, copy=False)
    revocation_reason = fields.Char(string='Revocation Reason', readonly=True, copy=False)

    # ── Verification ──
    verification_token = fields.Char(string='Verification Token', readonly=True, index=True, copy=False)
    verification_code = fields.Char(
        string='Verification Code', readonly=True, copy=False,
        compute='_compute_verification_code', store=True,
        help='Short human-comparable code (12 hex chars) derived from document '
             'number + revision + token. Printed on the stamp and shown on the '
             'verify page. NOT the PDF hash (avoids hash-circularity).')

    # ── Signed PDF (the exact bytes that were hashed — immutable) ──
    signed_attachment_id = fields.Many2one('ir.attachment', string='Signed PDF',
                                           readonly=True, copy=False, ondelete='restrict')

    _sql_constraints = [
        ('token_unique', 'unique(verification_token)', 'Verification token must be unique.'),
        ('move_unique', 'unique(move_id)', 'An invoice can only be signed once.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('document_uuid', 'SIG-%s' % secrets.token_hex(8).upper())
            vals.setdefault('verification_token', secrets.token_urlsafe(24))
            if not vals.get('signed_at'):
                vals['signed_at'] = fields.Datetime.now()
        return super().create(vals_list)

    @api.depends('document_number', 'revision', 'verification_token')
    def _compute_verification_code(self):
        import hashlib
        for rec in self:
            raw = '%s|%s|%s' % (rec.document_number or '', rec.revision, rec.verification_token or '')
            rec.verification_code = hashlib.sha256(raw.encode()).hexdigest()[:12].upper()

    def action_revoke(self, reason=''):
        """Revoke a signed document (evidence preserved, state changed).

        Called from the form button (no args) or programmatically with a
        reason.
        """
        for rec in self:
            if rec.state != 'signed':
                raise UserError(_('Only signed documents can be revoked.'))
            rec.write({
                'state': 'revoked',
                'revoked_at': fields.Datetime.now(),
                'revocation_reason': reason,
            })
            rec._log_event('REVOKED', detail=reason)

    def _log_event(self, event, detail=''):
        """Append to the immutable audit trail."""
        self.env['viva.document.audit'].create({
            'document_id': self.id,
            'event': event,
            'detail': detail,
        })

    def _get_verification_url(self):
        """Public verification URL for the QR code."""
        self.ensure_one()
        base = self.env['ir.config_parameter'].get_param(
            'vivafarm_document_sign.verify_base_url',
            self.env['ir.config_parameter'].get_param('web.base.url', ''),
        )
        return '%s/v/%s' % (base.rstrip('/'), self.verification_token)

    def _qr_data_uri(self):
        """QR code as a data URI for the report stamp (qrcode lib, ฿0).

        The QR contains ONLY the opaque verification token URL — never the
        PDF's own hash (avoiding hash-circularity) and never record IDs.
        """
        self.ensure_one()
        import base64
        from io import BytesIO

        import qrcode
        qr = qrcode.make(self._get_verification_url())
        buf = BytesIO()
        qr.save(buf, format='PNG')
        return 'data:image/png;base64,%s' % base64.b64encode(buf.getvalue()).decode()
