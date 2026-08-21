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

from ..services.signing_service import SigningService, sha256_hex

import base64

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
    _inherit = 'account.move'

    signed_document_id = fields.One2many(
        'viva.signed.document', 'move_id', string='Signed Documents',
        readonly=True)

    def _get_signed_documents(self):
        """Signed integrity records for this move."""
        return self.env['viva.signed.document'].search([('move_id', 'in', self.ids)])

    def _is_signed(self):
        """Whether this move has a signed integrity record."""
        return bool(self._get_signed_documents())

    def write(self, vals):
        """Reject substance changes on signed invoices (server-side lock)."""
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
            signed = self.env['viva.signed.document'].search(
                [('move_id', '=', self.id)], limit=1)
            if not signed:
                raise

        # 2. Render the STAMPED invoice (record exists -> hash block renders;
        # the customer signature is baked in via the context flag used by
        # the route when it writes the acknowledgment).
        pdf_bytes = self.env['ir.actions.report'].with_context(
            viva_show_stamp=True,
        )._render_qweb_pdf(
            report.report_name, [self.id])[0]
        pdf_hash = sha256_hex(pdf_bytes)

        # 3. Sign the exact stamped bytes
        sig_b64, _cert_info, _signed_at = service.sign_pdf(pdf_bytes)

        # 4. Store the stamped PDF (immutable — this is what printing returns)
        attachment = self.env['ir.attachment'].create({
            'name': '%s_signed.pdf' % self.name.replace('/', '_'),
            'datas': base64.b64encode(pdf_bytes),
            'res_model': 'account.move',
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
