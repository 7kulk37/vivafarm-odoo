"""account.payment — hash-only integrity record for the Payment Receipt.

The receipt is emitted automatically after a portal gateway payment and
emailed to the customer. Per user decision (2026-08-20) the receipt carries
a SELLER-SIDE hash only — NO RSA signature, NO customer signature. The
customer can verify the PDF bytes are the exact bytes emailed (upload →
hash compare on /v/<token>); the seller's identity is established by the
document itself, not by a cryptographic signature.

Same 4-step invariant as the SO/DN/invoice flows:
  1. PRE-CREATE the signed record (token + number known) so the next
     receipt render already carries the hash block.
  2. Render the STAMPED receipt PDF once — these exact bytes are emailed.
  3. SHA-256 those bytes (NO signature).
  4. Store the stamped PDF as the immutable attachment + the hash.
"""
import base64

from odoo import fields, models

from ..services.signing_service import sha256_hex


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    signed_document_id = fields.One2many(
        'viva.signed.document', 'payment_id', string='Signed Documents',
        readonly=True)

    def _is_signed(self):
        """Whether this payment has a hash-only integrity record."""
        return bool(self.env['viva.signed.document'].search([
            ('payment_id', 'in', self.ids),
        ], limit=1))

    def _hash_payment_receipt(self):
        """Render the receipt once, hash it, store as the immutable record.

        Called from the Omise _create_payment hook BEFORE the receipt email
        renders, so the emailed PDF already carries the hash block and the
        hash matches the exact emailed bytes.
        """
        self.ensure_one()
        # Idempotency guard: if a receipt record already exists (webhook
        # retry / cron race could call _create_payment twice), do NOT
        # create a duplicate or re-render — return the existing record.
        existing = self.env['viva.signed.document'].search([
            ('payment_id', '=', self.id),
            ('document_type', '=', 'payment_receipt'),
        ], limit=1)
        if existing:
            return existing
        # 1. Pre-create the record (token known before rendering)
        signed = self.env['viva.signed.document'].create({
            'document_number': self.name,
            'document_type': 'payment_receipt',
            'odoo_model': 'account.payment',
            'odoo_record_id': self.id,
            'payment_id': self.id,
            'revision': 1,
            'signer_user_id': self.env.user.id,
            'signed_at': fields.Datetime.now(),
        })
        # 2. Render the STAMPED receipt (record exists -> hash block renders)
        pdf_bytes = self.env['ir.actions.report'].with_context(
            viva_show_stamp=True,
        )._render_qweb_pdf(
            'vivafarm_report.viva_payment_receipt', [self.id])[0]
        pdf_hash = sha256_hex(pdf_bytes)
        # 3. NO signature — hash only (user decision 2026-08-20)
        # 4. Store the stamped PDF + hash
        attachment = self.env['ir.attachment'].create({
            'name': '%s_receipt.pdf' % self.name.replace('/', '_'),
            'datas': base64.b64encode(pdf_bytes),
            'res_model': 'account.payment',
            'res_id': self.id,
            'type': 'binary',
        })
        signed.write({
            'pdf_sha256': pdf_hash,
            'signed_attachment_id': attachment.id,
        })
        signed._log_event('HASHED', detail='sha256=%s' % pdf_hash[:16])
        return signed
