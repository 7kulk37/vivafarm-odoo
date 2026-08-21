"""stock.picking extensions — customer delivery acknowledgment hash.

When the customer acknowledges receipt of a delivery via the portal
(ใบส่งสินค้า receipt proof, ป.พ.พ. มาตรา 456), the drawn signature is
written on the picking, then the delivery note PDF is rendered once,
SHA-256'd, RSA-signed, and stored — the printed delivery note then
carries the "Digitally Signed Document" hash block proving the exact
bytes the customer accepted as received.

Chained to the linked SO (user request 2026-08-18): the signed delivery
record ALSO carries sale_order_id (from picking.sale_id), and the stamp
shows the linked SO + its verification code — so an auditor can verify
both documents from one page.

Only portal-signed deliveries (signature set) are hashed. A backend
validation without a customer signature produces no hash block.

Lock: once hashed, substance changes (partner, dates, origin, move
lines) are rejected at ORM level, AND the picking cannot be cancelled
(user decision 2026-08-18 — the goods were received).
"""
from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services.signing_service import SigningService, sha256_hex

import base64

from psycopg2 import IntegrityError

#: Fields that define the substance of a delivered picking. If any of
#: these change after the customer's acknowledgment is hashed, the
#: evidence no longer matches the received delivery.
PROTECTED_FIELDS = {
    'partner_id', 'scheduled_date', 'date_done', 'origin',
    'move_ids', 'move_line_ids', 'location_id', 'location_dest_id',
    'picking_type_id', 'note',
}


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    signed_document_id = fields.One2many(
        'viva.signed.document', 'picking_id', string='Signed Documents',
        readonly=True)

    def _is_signed(self):
        """Whether this picking has a signed integrity record."""
        return bool(self.env['viva.signed.document'].search([
            ('picking_id', 'in', self.ids),
        ], limit=1))

    def _hash_delivery_accepted(self):
        """Render the acknowledged delivery note once, hash + sign, store.

        Same 4-step invariant as the invoice/SO sign flows:
          1. PRE-CREATE the signed record (token + number known) so the
             next PDF render already carries the hash block.
          2. Render the STAMPED delivery note PDF once — these exact
             bytes are the acknowledged document.
          3. SHA-256 + RSA sign those bytes.
          4. Store the stamped PDF as the immutable attachment and write
             the crypto evidence onto the record.
        After this, printing serves the STORED bytes (ir_actions_report
        override) — so print == acknowledged == verified, byte-for-byte.
        """
        self.ensure_one()
        service = SigningService(self.env)
        cert_info = service.backend.certificate_info()

        # 1. Pre-create the record (token + identity known before rendering)
        # DB-layer race (same class as the SO/invoice paths, guard 3): a
        # concurrent sign of the SAME picking raises IntegrityError on the
        # unique(picking_id) constraint. Converge — reuse the winner's
        # record instead of crashing.
        try:
            with self.env.cr.savepoint():
                signed = self.env['viva.signed.document'].create({
                    'document_number': self.name,
                    'document_type': 'delivery_note',
                    'odoo_model': 'stock.picking',
                    'odoo_record_id': self.id,
                    'picking_id': self.id,
                    'sale_order_id': self.sale_id.id,
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
            signed = self.env['viva.signed.document'].search(
                [('picking_id', '=', self.id)], limit=1)
            if not signed:
                raise

        # 2. Render the STAMPED delivery note (record exists -> hash block
        # renders; the receiver signature is baked in via the context flag
        # used by the route when it writes the acknowledgment).
        pdf_bytes = self.env['ir.actions.report'].with_context(
            viva_show_stamp=True,
        )._render_qweb_pdf(
            'vivafarm_report.viva_delivery_note', [self.id])[0]
        pdf_hash = sha256_hex(pdf_bytes)

        # 3. Sign the exact stamped bytes
        sig_b64, _cert_info, _signed_at = service.sign_pdf(pdf_bytes)

        # 4. Store the stamped PDF (immutable — this is what printing returns)
        attachment = self.env['ir.attachment'].create({
            'name': '%s_signed.pdf' % self.name.replace('/', '_'),
            'datas': base64.b64encode(pdf_bytes),
            'res_model': 'stock.picking',
            'res_id': self.id,
            'type': 'binary',
        })
        signed.write({
            'pdf_sha256': pdf_hash,
            'signature_b64': sig_b64,
            'public_key_pem': service.backend.public_key_pem(),
            'signed_attachment_id': attachment.id,
        })

        signed._log_event('SIGNED', detail='sha256=%s' % pdf_hash[:16])

    def write(self, vals):
        """Reject substance changes on signed deliveries (server-side lock).

        State transitions stay allowed EXCEPT cancel — the customer
        acknowledged receipt, so the delivery cannot be cancelled after
        signing (user decision 2026-08-18).
        """
        signed = self.filtered(lambda p: p._is_signed())
        if signed:
            protected_changed = set(vals.keys()) & PROTECTED_FIELDS
            if 'move_ids' in vals:
                for cmd in vals['move_ids']:
                    if cmd[0] in (2, 3, 5):  # unlink, unlink-one, clear
                        protected_changed.add('move_ids')
            if protected_changed:
                raise UserError(_(
                    'This delivery note has been SIGNED by the customer and '
                    'locked. The received delivery cannot be changed.'))
        return super().write(vals)

    def action_cancel(self):
        """Block cancelling a signed delivery — the goods were received."""
        signed = self.filtered(lambda p: p._is_signed())
        if signed:
            raise UserError(_(
                'This delivery note has been SIGNED by the customer '
                '(goods received) and cannot be cancelled.'))
        return super().action_cancel()

    @staticmethod
    def _is_test_cert(cert_info):
        return 'Test' in cert_info.get('subject', '') or 'Test' in cert_info.get('issuer', '')

    @staticmethod
    def _to_odoo_datetime(iso_str):
        """Convert ISO-8601 to Odoo Datetime string (naive UTC)."""
        from datetime import datetime, timezone
        if not iso_str:
            return False
        try:
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            return False
