"""viva.signed.document — integrity record for a signed tax invoice.

One record per signed invoice. Stores the cryptographic evidence:
document hash, detached RSA signature, certificate metadata, revision
chain, and the verification token used by the public /v/<token> page.

Migration-ready: certificate fields are generic (type/issuer/serial/
fingerprint), so swapping the TEST self-signed cert for a Thai CA cert
is a config/trust change, not a schema change.
"""
import base64
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from psycopg2 import IntegrityError

from ..services.signing_service import SigningService, sha256_hex


class VivaSignedDocument(models.Model):
    _name = 'viva.signed.document'
    _description = 'Signed Document (Tax Invoice integrity record)'
    _order = 'signed_at desc, id desc'

    # ── Document identity ──
    document_uuid = fields.Char(string='Document UUID', readonly=True, copy=False)
    document_type = fields.Selection([
        ('tax_invoice', 'Tax Invoice'),
        ('sale_order', 'Sale Order'),
        ('delivery_note', 'Delivery Note'),
        ('invoice', 'Invoice (ใบแจ้งหนี้)'),
        ('payment_receipt', 'Payment Receipt'),
        ('payment_slip', 'Payment Slip (hand-signed upload)'),
    ], string='Document Type', required=True, default='tax_invoice')
    channel = fields.Selection([
        ('digital', 'Digital signature (portal)'),
        ('manual', 'Manual upload (hand-signed paper copy)'),
    ], string='Sealing Channel', required=True, default='digital',
        help='How the document was sealed. Manual uploads seal the EXACT '
             'bytes the customer submitted (hash only, no RSA signature — '
             'same evidence model as the payment receipt).')
    document_number = fields.Char(string='Document Number', readonly=True, copy=False)
    odoo_model = fields.Char(string='Odoo Model', readonly=True, default='account.move')
    odoo_record_id = fields.Integer(string='Odoo Record ID', readonly=True, index=True)
    move_id = fields.Many2one('account.move', string='Invoice', ondelete='restrict', index=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order',
                                    ondelete='restrict', index=True)
    picking_id = fields.Many2one('stock.picking', string='Delivery Note',
                                 ondelete='restrict', index=True)
    payment_id = fields.Many2one('account.payment', string='Payment',
                                 ondelete='restrict', index=True)

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
    signer_user_id = fields.Many2one('res.users', string='Signed By (Odoo User)', readonly=True)
    signer_name = fields.Char(
        string='Signer Name', readonly=True, copy=False,
        help='The customer\'s typed name (from the portal signature form). '
             'The portal routes are auth="public", so signer_user_id is the '
             'public user (OdooBot) — the human identity lives here.')
    signer_position = fields.Char(
        string='Signer Position', readonly=True, copy=False,
        help='The customer\'s typed position (from the portal signature form).')
    # Manual-upload evidence (channel='manual'): the person who submitted the
    # hand-signed paper copy + the network metadata captured at upload time.
    # Legal note (2026-08-21, Thai law consultant memo): the typed name +
    # confirmation checkbox raise ETA B.E.2544 §9/§11 originator weight — the
    # upload moves from "submitted via link X" to "submitted by a person who
    # identified against the order". IP/UA are retained per ETA §12(3).
    uploader_name = fields.Char(
        string='Uploaded by (typed)', readonly=True, copy=False,
        help='The customer typed name on the manual-upload form. '
             'Required — turns "uploaded via link" into "uploaded by a person".')
    uploader_ip = fields.Char(string='Upload IP', readonly=True, copy=False)
    uploader_user_agent = fields.Char(string='Upload User-Agent', readonly=True, copy=False)
    source_filename = fields.Char(string='Source File Name', readonly=True, copy=False)
    source_mimetype = fields.Char(string='Source MIME Type', readonly=True, copy=False)
    seller_note = fields.Text(string='Seller Note', copy=False,
                              help='Seller-side annotation (e.g. "customer '
                                   'hand-signed in store on …", "received via '
                                   'Line") — a contemporaneous business record.')
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

    # DB-layer guard (user request 2026-08-17, v19.0.1.0.4): the Odoo 19
    # nightly DROPPED the _sql_constraints compat shim — the old
    # `_sql_constraints = [('so_unique', 'unique(sale_order_id)', ...)]`
    # silently never created any DB constraint (pg_constraint had only FKs),
    # so a duplicate sign could create TWO signed documents for one order.
    # models.Constraint is the Odoo 19 syntax and physically applies the
    # UNIQUE index during registry setup. PostgreSQL then rejects a second
    # signed document atomically — the strongest of the three guards
    # (server idempotency + customer JS one-shot + this DB constraint).
    # Naming convention: `_<name>` attribute -> constraint
    # `viva_signed_document_<name>` (see table_objects.Constraint.full_name).
    # Sale-order uniqueness must only bind for actual sale_order documents —
    # the delivery_note signed record ALSO carries sale_order_id as the
    # record-level chain link, and would otherwise collide with the SO's own
    # signed record (verified 2026-08-18: DN sign raised
    # "A sale order can only be signed once.").
    # A UNIQUE constraint cannot be partial, so the guard is a partial
    # unique index created in _auto_init (see below).
    _token_unique = models.Constraint(
        'UNIQUE (verification_token)',
        'Verification token must be unique.',
    )
    _move_unique = models.Constraint(
        'UNIQUE (move_id)',
        'An invoice can only be signed once.',
    )
    _picking_unique = models.Constraint(
        'UNIQUE (picking_id)',
        'A delivery note can only be signed once.',
    )

    def _auto_init(self):
        res = super()._auto_init()
        self.env.cr.execute("""
            DROP INDEX IF EXISTS viva_signed_document_so_unique;
            CREATE UNIQUE INDEX IF NOT EXISTS viva_signed_document_so_unique_partial
                ON viva_signed_document (sale_order_id)
                WHERE document_type = 'sale_order'
        """)
        return res

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

    @api.model
    def _create_manual_record(self, model, record_id, document_type,
                              document_number, filename, mimetype, data,
                              uploader_name, uploader_ip='', uploader_agent='',
                              seller_note=''):
        """Seal an uploaded hand-signed paper copy (channel='manual').

        Same 4-step invariant as every other sign flow, but hashes the EXACT
        uploaded bytes (no re-render, no RSA signature — hash-only, like the
        payment receipt):
          1. PRE-CREATE the record (token + number known) so the verification
             token/code exist before storing the file.
          2. SHA-256 the exact uploaded bytes.
          3. Store the bytes as the immutable attachment.
          4. Write the hash + source metadata onto the record.

        Legal model (2026-08-21, Thai law consultant memo): the claims are
        ONLY (a) these exact bytes were submitted through the token-linked
        portal at time T, (b) they are unaltered since (SHA-256), (c)
        re-checkable anytime. The typed uploader_name + network metadata are
        captured per ETA B.E.2544 §9/§11/§12(3).

        Returns the sealed record (converges on the winner when a duplicate
        upload races the DB unique constraint).
        """
        # Idempotency guard — one sealed record per (model, record, type).
        # A document is sealed ONCE, by whichever method: the UNIQUE(move_id)
        # / UNIQUE(picking_id) / partial-UNIQUE(sale_order_id) constraints
        # guarantee it at DB level, so a manual upload on an already-digital
        # sealed doc converges on the existing record (and vice-versa).
        existing = self.sudo().search([
            ('odoo_model', '=', model),
            ('odoo_record_id', '=', record_id),
            ('document_type', '=', document_type),
        ], limit=1)
        if existing:
            return existing
        if not data:
            raise UserError(_('No file data received.'))
        try:
            with self.env.cr.savepoint():
                # Link field mirrors the digital paths (move_id /
                # sale_order_id / picking_id) so the verify page's
                # Previous/Next chain treats manual records uniformly.
                link_vals = {}
                if model == 'account.move':
                    link_vals['move_id'] = record_id
                elif model == 'sale.order':
                    link_vals['sale_order_id'] = record_id
                elif model == 'stock.picking':
                    link_vals['picking_id'] = record_id
                elif model == 'payment.transaction':
                    tx = self.env['payment.transaction'].browse(record_id)
                    if tx.payment_id:
                        link_vals['payment_id'] = tx.payment_id.id
                signed = self.env['viva.signed.document'].create({
                    'document_number': document_number,
                    'document_type': document_type,
                    'channel': 'manual',
                    'odoo_model': model,
                    'odoo_record_id': record_id,
                    'revision': 1,
                    'signer_name': uploader_name,
                    'uploader_name': uploader_name,
                    'uploader_ip': uploader_ip,
                    'uploader_user_agent': uploader_agent,
                    'source_filename': filename,
                    'source_mimetype': mimetype,
                    'seller_note': seller_note,
                    'signed_at': fields.Datetime.now(),
                    **link_vals,
                })
        except IntegrityError:
            signed = self.env['viva.signed.document'].search([
                ('odoo_model', '=', model),
                ('odoo_record_id', '=', record_id),
                ('document_type', '=', document_type),
            ], limit=1)
            if not signed:
                raise

        pdf_hash = sha256_hex(data)
        # Draft invoices have name=False in Odoo 19 until posted — never
        # crash on a non-string document_number (edge test E15 caught the
        # 500: 'bool' object has no attribute 'replace').
        safe_doc_number = str(document_number or 'doc_%s' % record_id)
        attachment = self.env['ir.attachment'].create({
            'name': '%s_%s' % (safe_doc_number.replace('/', '_'), filename or 'upload'),
            'datas': base64.b64encode(data),
            'res_model': 'viva.signed.document',
            'res_id': signed.id,
            'type': 'binary',
        })
        signed.write({
            'pdf_sha256': pdf_hash,
            'signed_attachment_id': attachment.id,
        })
        signed._log_event('MANUAL_UPLOAD', detail='sha256=%s' % pdf_hash[:16])
        return signed

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
