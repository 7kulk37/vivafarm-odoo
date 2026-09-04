"""account.move extensions — server-side lock for signed tax invoices.

The lock is the "hash links back to an uneditable transaction" guarantee:
once an invoice is signed, changing its financial substance is rejected at
the ORM level (UI readonly is bypassable; this is not).

Critical legal constraint (ป.86/2542 ข้อ 25): correction of a signed
invoice is NEVER an edit — it is void + reissue with a NEW number and the
SAME date. The reissue path (vivafarm_report's action_reissue, which
creates a new move with reissue_root_id) stays OPEN. Only edits to the
signed move itself are blocked.

Also hosts the customer invoice acknowledgment hash (ใบแจ้งหนี้ commercial
invoice, EVIDENCE-ONLY per lawyer sign-off 2026-08-19): the customer's
drawn signature is written on the move, then the invoice PDF is rendered
once, SHA-256'd, RSA-signed, and stored — the printed invoice then carries
the "Digitally Signed Document" hash block proving the exact bytes the
customer acknowledged as the amount due. The acknowledgment is OPTIONAL and
NEVER gates payment: refusal = chatter note + no state change.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.signing_service import SigningService

from psycopg2 import IntegrityError

#: Fields that define the financial substance of a tax invoice. If any of
#: these change on a signed move, the signature evidence is void.
PROTECTED_FIELDS = {
    'partner_id', 'invoice_date', 'date', 'ref', 'narration',
    'invoice_line_ids', 'line_ids', 'amount_total', 'amount_untaxed',
    'amount_tax', 'currency_id', 'journal_id', 'payment_reference',
    'invoice_payment_term_id', 'fiscal_position_id',
}


class AccountMove(models.Model):
    _inherit = ['account.move', 'viva.sign.mixin']

    signed_document_id = fields.One2many(
        'viva.signed.document', 'move_id', string='Signed Documents',
        readonly=True)

    def _get_signed_documents(self):
        """Signed integrity records for this move."""
        return self.env['viva.signed.document'].search([('move_id', 'in', self.ids)])

    def _sealed_document(self):
        """The ONE seal record for this move (invoice or tax_invoice), any channel.

        sudo: see ``write()`` docstring. The signed-document lookup is an
        integrity check, not a user action — must not be gated on access.
        """
        return self.env['viva.signed.document'].sudo().search([
            ('move_id', '=', self.id),
            ('document_type', 'in', ('invoice', 'tax_invoice')),
        ], limit=1)

    def _is_signed(self):
        """Whether this move has a signed integrity record."""
        return bool(self._sealed_document())

    def write(self, vals):
        """Reject substance changes on signed invoices (server-side lock).

        IMPORTANT: the signed-document lookup MUST use sudo(). It is an
        integrity check, not a user action — gating it on user access would
        block posting any invoice for users who lack signed-document
        visibility (e.g. the founder without 'Show Full Accounting Features').
        The access rule still protects the records themselves (read/write
        from the UI); only the integrity check inside account.move.write
        bypasses it.
        """
        signed = self.filtered(lambda m: m._is_signed())
        if signed:
            protected_changed = set(vals.keys()) & PROTECTED_FIELDS
            # Deleting lines is a substance change too
            if 'line_ids' in vals:
                for cmd in vals['line_ids']:
                    if cmd[0] in (2, 3, 5):  # unlink, unlink-one, clear
                        protected_changed.add('line_ids')
            if protected_changed:
                raise UserError(_(
                    'This tax invoice has been SIGNED and locked. '
                    'Financial fields cannot be changed. '
                    'To correct it, void and re-issue with a new number '
                    '(ป.86/2542 ข้อ 25).'))
        return super().write(vals)

    def button_draft(self):
        """Block reset-to-draft on signed invoices.

        Odoo allows posted→draft reset (corrections). For a signed invoice
        this would silently break the integrity evidence — the only legal
        correction path is void + reissue (ป.86/2542 ข้อ 25).
        """
        signed = self.filtered(lambda m: m._is_signed())
        if signed:
            raise UserError(_(
                'This tax invoice has been SIGNED and cannot be reset to '
                'draft. To correct it, void and re-issue with a new number '
                '(ป.86/2542 ข้อ 25).'))
        return super().button_draft()

    def _post(self, soft=True):
        """When posting, if this move replaces a signed invoice (reissue),
        nothing extra needed — the NEW move gets its own signature later.
        """
        return super()._post(soft=soft)

    def _hash_invoice_accepted(self):
        """Render the acknowledged invoice once, hash + sign, store.

        Same 4-step invariant as the SO/DN sign flows:
          1. PRE-CREATE the signed record (token + number known) so the
             next PDF render already carries the hash block.
          2. Render the STAMPED invoice PDF once — these exact bytes are
             the acknowledged document.
          3. SHA-256 + RSA sign those bytes.
          4. Store the stamped PDF as the immutable attachment and write
             the crypto evidence onto the record.
        After this, printing serves the STORED bytes (ir_actions_report
        override) — so print == acknowledged == verified, byte-for-byte.
        """
        self.ensure_one()
        service = SigningService(self.env)
        cert_info = service.backend.certificate_info()

        # Minimal flow (2026-08-21): the customer's invoice report field
        # decides WHICH document gets signed. A minimal-flow customer has it
        # set to the Tax invoice (ใบกำกับภาษี) 3 copied report — the signed
        # record is document_type 'tax_invoice' and the stored-bytes override
        # branch for viva_invoice serves it on every channel. Standard flow
        # (report unset) keeps the plain Invoice (ใบแจ้งหนี้) + 'invoice'.
        report = self._get_viva_invoice_report()
        doc_type = ('tax_invoice' if report
                    and report.report_name == 'vivafarm_report.viva_invoice'
                    else 'invoice')

        # One seal per doc (any channel) — if this exact document_type is
        # already sealed (manual hand-signed upload first, or a prior digital
        # sign), return it. Never overwrite a manual hash-only record with
        # RSA signature fields (review seam fix, 2026-08-24).
        existing = self.env['viva.signed.document'].search([
            ('move_id', '=', self.id),
            ('document_type', '=', doc_type),
        ], limit=1)
        if existing:
            return existing

        # 1. Pre-create the record (token + identity known before rendering)
        # DB-layer race (same class as the SO/DN paths, guard 3): a
        # concurrent sign of the SAME invoice raises IntegrityError on the
        # unique(move_id) constraint. Converge — reuse the winner's
        # record instead of crashing.
        try:
            with self.env.cr.savepoint():
                signed = self.env['viva.signed.document'].create({
                    'document_number': self.name,
                    'document_type': doc_type,
                    'odoo_model': 'account.move',
                    'odoo_record_id': self.id,
                    'move_id': self.id,
                    'revision': 1,
                    'certificate_type': 'TEST' if self._is_test_cert(cert_info) else 'PRODUCTION',
                    'certificate_subject': cert_info['subject'],
                    'certificate_issuer': cert_info['issuer'],
                    'certificate_serial': cert_info['serial'],
                    'certificate_fingerprint': cert_info['fingerprint'],
                    'certificate_valid_from': self._to_odoo_datetime(cert_info['not_before']),
                    'certificate_valid_to': self._to_odoo_datetime(cert_info['not_after']),
                    'signer_user_id': self.env.user.id,
                    'signer_name': self.signed_by or '',
                    'signer_position': self.signed_position or '',
                    'signed_at': fields.Datetime.now(),
                })
        except IntegrityError:
            signed = self._sealed_document()
            if not signed:
                raise

        # 2–4. Render the STAMPED invoice once, hash + RSA sign those exact
        # bytes, store as the immutable attachment + crypto evidence
        # (shared 4-step invariant — see VivaSignMixin._sign_and_store).
        # report is the customer's invoice report (minimal flow: tax
        # invoice; standard flow: plain invoice).
        self._sign_and_store(self, signed, service,
                             report_name=report.report_name)
