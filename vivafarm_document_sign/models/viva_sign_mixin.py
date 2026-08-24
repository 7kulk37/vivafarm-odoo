"""Shared signing helpers for vivafarm_document_sign (Odoo AbstractModel mixin).

Pure certificate helpers that were copy-pasted across account.move,
sale.order, stock.picking and the sign wizard (review dedup, 2026-08-24).
No state — safe to inherit anywhere in vivafarm_document_sign.

MUST be an AbstractModel consumed via `_inherit`, NOT a plain Python base
class — Odoo's registry setup rebases model __bases__ and a plain mixin
breaks the merge (verified on staging 2026-08-24).
"""
import base64

from odoo import models

from ..services.signing_service import SigningService, sha256_hex


class VivaSignMixin(models.AbstractModel):
    _name = 'viva.sign.mixin'
    _description = 'VivaFarm signing certificate helpers'

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

    def _sign_and_store(self, record, signed, service, report_name=None,
                        pdf_bytes=None):
        """Steps 2–4 of the 4-step digital seal invariant (shared, 2026-08-24).

        Caller pre-created `signed` (step 1) so the hash block renders, then
        this renders the STAMPED PDF once (or consumes caller-supplied
        `pdf_bytes` — the wizard renders via its own method), SHA-256 + RSA
        signs those exact bytes, stores them as the immutable attachment, and
        writes the crypto evidence onto the record. The report override then
        serves the STORED bytes on every channel — print == signed ==
        verified, byte-for-byte.

        `record` = the business record (account.move / sale.order /
        stock.picking) whose PDF is hashed; `service` = the SigningService;
        `report_name` = the QWeb report to render (ignored when pdf_bytes
        given).
        """
        self.ensure_one()
        pdf_bytes = pdf_bytes or self.env['ir.actions.report'].with_context(
            viva_show_stamp=True,
        )._render_qweb_pdf(report_name, [record.id])[0]
        pdf_hash = sha256_hex(pdf_bytes)
        sig_b64, _cert_info, _signed_at = service.sign_pdf(pdf_bytes)
        attachment = self.env['ir.attachment'].create({
            'name': '%s_signed.pdf' % str(record.name or signed.document_number).replace('/', '_'),
            'datas': base64.b64encode(pdf_bytes),
            'res_model': record._name,
            'res_id': record.id,
            'type': 'binary',
        })
        signed.write({
            'pdf_sha256': pdf_hash,
            'signature_b64': sig_b64,
            'public_key_pem': service.backend.public_key_pem(),
            'signed_attachment_id': attachment.id,
        })
        signed._log_event('SIGNED', detail='sha256=%s' % pdf_hash[:16])
        return signed
