"""sale.order extensions — customer-acceptance hash for signed quotations.

When the customer accepts a quotation via the portal (sale portal
/accept route), the acceptance IS the intent (ETDA B.E. 2544 §26): the
customer's signature is written on the SO, then action_confirm moves it
to 'sale'. At that moment we render the SO PDF once, SHA-256 it, RSA
sign it, and store the evidence — the printed SO then carries the
"Digitally Signed Document" hash block proving the exact bytes the
customer accepted (CCC §456 written evidence).

Only portal-signed orders (signature set) are hashed. A backend user
confirming without a customer signature produces no hash block.

Lock: once hashed, substance changes (partner, lines, amounts, dates,
pricelist, terms) are rejected at ORM level — the accepted contract is
frozen. A counter-offer (CCC §359) is a NEW quotation, not an edit.
"""
from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services.signing_service import SigningService

from psycopg2 import IntegrityError

#: Fields that define the substance of an accepted sale order. If any of
#: these change after the customer's acceptance is hashed, the evidence
#: no longer matches the accepted contract.
PROTECTED_FIELDS = {
    'partner_id', 'partner_shipping_id', 'date_order', 'commitment_date',
    'validity_date', 'client_order_ref', 'note', 'order_line',
    'pricelist_id', 'payment_term_id', 'fiscal_position_id',
    'amount_total', 'amount_untaxed', 'amount_tax', 'currency_id',
}


class SaleOrder(models.Model):
    _inherit = ['sale.order', 'viva.sign.mixin']

    signed_document_id = fields.One2many(
        'viva.signed.document', 'sale_order_id', string='Signed Documents',
        readonly=True)

    def _sealed_document(self):
        """The ONE seal record for this order, any channel (one seal per doc).

        Scoped by document_type='sale_order' — the delivery_note's chain
        link (sale_order_id on the DN record) must NOT count as this order's
        own seal (review seam fix, 2026-08-24).

        sudo: same integrity-check rationale as
        ``vivafarm_document_sign/models/account_move.py``.
        """
        return self.env['viva.signed.document'].sudo().search([
            ('sale_order_id', '=', self.id),
            ('document_type', '=', 'sale_order'),
        ], limit=1)

    def _is_signed(self):
        """Whether this order has its OWN signed integrity record."""
        return bool(self._sealed_document())

    def action_confirm(self):
        """Confirm the order; if the customer accepted via portal, hash it.

        The portal acceptance route writes `signature` on the SO before
        calling _validate_order -> action_confirm. That signature is the
        intent marker: only orders carrying it get hashed here.
        """
        res = super().action_confirm()
        for order in self.filtered(
            lambda so: so.state == 'sale' and so.signature and not so._is_signed()
        ):
            order._hash_customer_accepted()
        return res

    def _hash_customer_accepted(self):
        """Render the accepted SO once, hash + sign it, store evidence, lock.

        Order matters (same invariant as the invoice sign flow):
          1. PRE-CREATE the signed record (token + number known) so the
             next PDF render already carries the hash block.
          2. Render the STAMPED SO PDF once — these exact bytes are the
             accepted document.
          3. SHA-256 + RSA sign those bytes.
          4. Store the stamped PDF as the immutable attachment and write
             the crypto evidence onto the record.
        After this, printing serves the STORED bytes (ir_actions_report
        override) — so print == accepted == verified, byte-for-byte.
        """
        self.ensure_one()
        service = SigningService(self.env)
        cert_info = service.backend.certificate_info()

        # One seal per doc (any channel) — if a seal already exists (manual
        # hand-signed upload first, or a prior digital sign), the document
        # is already sealed; return it. Never overwrite a manual hash-only
        # record with RSA signature fields (review seam fix, 2026-08-24).
        existing = self._sealed_document()
        if existing:
            return existing

        # 1. Pre-create the record (token + identity known before rendering)
        # DB-layer race: two concurrent sign attempts for the SAME order both
        # pass `not so._is_signed()` (neither committed yet), then both
        # create(). The unique(sale_order_id) constraint lets exactly ONE
        # succeed; the loser raises IntegrityError. Converge instead of
        # crashing: roll back to the savepoint and reuse the winner's record
        # (its stored bytes are the accepted document — byte-identical to
        # what this loser would have produced).
        try:
            with self.env.cr.savepoint():
                signed = self.env['viva.signed.document'].create({
                    'document_number': self.name,
                    'document_type': 'sale_order',
                    'odoo_model': 'sale.order',
                    'odoo_record_id': self.id,
                    'sale_order_id': self.id,
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

        # 2–4. Render the STAMPED SO PDF once, hash + RSA sign those exact
        # bytes, store as the immutable attachment + crypto evidence
        # (shared 4-step invariant — see VivaSignMixin._sign_and_store).
        self._sign_and_store(self, signed, service,
                             report_name='vivafarm_report.viva_quotation_so')

    def write(self, vals):
        """Reject substance changes on hashed orders (server-side lock)."""
        signed = self.filtered(lambda so: so._is_signed())
        if signed:
            protected_changed = set(vals.keys()) & PROTECTED_FIELDS
            if 'order_line' in vals:
                for cmd in vals['order_line']:
                    if cmd[0] in (2, 3, 5):  # unlink, unlink-one, clear
                        protected_changed.add('order_line')
            if protected_changed:
                raise UserError(_(
                    'This sale order has been SIGNED by the customer and '
                    'locked. The accepted contract cannot be changed. '
                    'A counter-offer must be a new quotation (CCC §359).'))
        return super().write(vals)
