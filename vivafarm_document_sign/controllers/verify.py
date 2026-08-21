"""Public document verification — GET /v/<token>.

NO Odoo login required (that's the point: auditors, customers, and
accountants can validate a tax invoice without an ERP account).

Two checks on one page:
  1. Hash check — the uploaded/queried PDF is re-hashed and compared to
     the stored SHA-256 recorded at signing time.
  2. Signature check — the stored detached RSA signature is verified
     against the stored public key (cryptography lib).

The page never exposes record IDs or internal fields beyond the evidence.
"""
import base64
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class VivaVerificationController(http.Controller):

    @http.route('/v/<token>', type='http', auth='public', website=False,
                csrf=False, methods=['GET', 'POST'])
    def verify(self, token, **kwargs):
        """Render verification result; POST carries an uploaded PDF copy."""
        signed = request.env['viva.signed.document'].sudo().search(
            [('verification_token', '=', token)], limit=1)
        if not signed:
            return request.not_found()

        result = {
            'document_number': signed.document_number,
            'document_type': signed.document_type,
            'revision': signed.revision,
            'verification_code': signed.verification_code,
            'state': signed.state,
            'signed_at': signed.signed_at,
            'signer': signed.signer_name or (signed.signer_user_id.name if signed.signer_user_id else ''),
            'signer_position': signed.signer_position or '',
            'certificate_subject': signed.certificate_subject,
            'certificate_issuer': signed.certificate_issuer,
            'certificate_type': signed.certificate_type,
            'pdf_sha256': signed.pdf_sha256,
            'odoo_record_locked': True,  # signed => lock enforced at ORM level
            'previous_linked': self._get_previous_linked_document(signed),
            'next_linked': self._get_next_linked_document(signed),
        }

        # Signature verification (independent of upload — always shown).
        # Hash-only documents (payment_receipt) have NO signature — the
        # page shows "HASH RECORD (SELLER-SIDE)" instead of a signature badge.
        # Manual hand-signed uploads (channel='manual') are hash-only too —
        # the page shows "MANUAL UPLOAD — HAND-SIGNED PAPER COPY" plus the
        # uploader/source rows and the lawyer-approved disclaimer (no
        # signature authenticity claims, Thai law memo 2026-08-21).
        if signed.channel == 'manual':
            result['is_manual_upload'] = True
            result['is_hash_only'] = False
            result['signature_valid'] = None
            result['uploader_name'] = signed.uploader_name
            result['source_filename'] = signed.source_filename
        elif signed.document_type == 'payment_receipt':
            result['is_manual_upload'] = False
            result['is_hash_only'] = True
            result['signature_valid'] = None
        else:
            result['is_manual_upload'] = False
            result['is_hash_only'] = False
            result['signature_valid'] = self._verify_signature(signed)

        # Upload-compare (the real hash proof)
        uploaded = kwargs.get('uploaded_file')
        result['uploaded'] = False
        result['hash_match'] = None
        if uploaded and hasattr(uploaded, 'read'):
            data = uploaded.read()
            result['uploaded'] = True
            import hashlib
            result['uploaded_sha256'] = hashlib.sha256(data).hexdigest()
            result['hash_match'] = (result['uploaded_sha256'] == signed.pdf_sha256)

        signed._log_event('VERIFIED')
        return request.render('vivafarm_document_sign.verification_page', result)

    def _link_dict(self, signed):
        if not signed:
            return {}
        return {
            'document_number': signed.document_number,
            'verification_code': signed.verification_code,
            'url': '/v/%s' % signed.verification_token,
        }

    def _get_previous_linked_document(self, signed):
        """Find the PREVIOUS signed document in the record-level flow.

        Record-level linkage only (user decision 2026-08-20) — no crypto
        chain. Rules (walk backwards):
          - Delivery Note -> its parent Sale Order (SO signed doc).
          - Invoice / Tax Invoice -> the signed Delivery Note for that SO
            (fallback: the signed SO itself). The minimal-flow tax invoice
            (document_type 'tax_invoice', 2026-08-21) must resolve exactly
            like the plain Invoice — before the v20 fix it fell into the
            else branch and the verify page showed '-' on both links.
          - Payment Receipt -> the signed Invoice/Tax Invoice behind the
            payment's reconciled invoice(s).
          - Otherwise / no link -> empty dict (template renders '-').
        """
        Model = self.env['viva.signed.document'].sudo()
        if signed.document_type == 'delivery_note' and signed.sale_order_id:
            prev = Model.search([
                ('sale_order_id', '=', signed.sale_order_id.id),
                ('document_type', '=', 'sale_order'),
            ], limit=1)
        elif signed.document_type in ('invoice', 'tax_invoice') and signed.move_id:
            so = signed.move_id.line_ids.mapped('sale_line_ids.order_id')[:1]
            prev = None
            if so:
                prev = Model.search([
                    ('sale_order_id', '=', so.id),
                    ('document_type', '=', 'delivery_note'),
                ], limit=1)
                if not prev:
                    prev = Model.search([
                        ('sale_order_id', '=', so.id),
                        ('document_type', '=', 'sale_order'),
                    ], limit=1)
        elif signed.document_type in ('payment_receipt', 'payment_slip') and signed.payment_id:
            inv = signed.payment_id.reconciled_invoice_ids[:1]
            prev = None
            if inv:
                prev = Model.search([
                    ('move_id', '=', inv.id),
                    ('document_type', 'in', ('invoice', 'tax_invoice')),
                ], limit=1)
        else:
            prev = None
        return self._link_dict(prev)

    def _get_next_linked_document(self, signed):
        """Find the NEXT signed document in the record-level flow.

        Rules (walk forwards):
          - Sale Order -> the signed Delivery Note for it (fallback:
            the signed Invoice/Tax Invoice(s) for that SO).
          - Delivery Note -> the signed Invoice/Tax Invoice for that SO.
          - Invoice / Tax Invoice -> the signed Payment Receipt for its
            reconciled payment(s). Uses reconciled_payment_ids (a v20 fix:
            move.payment_ids is the One2many of payments whose journal-entry
            move is this move — always empty for reconciled invoices, so the
            Next link never resolved for a paid invoice).
          - Otherwise / no link -> empty dict (template renders '-').
        """
        Model = self.env['viva.signed.document'].sudo()
        if signed.document_type == 'sale_order' and signed.sale_order_id:
            nxt = Model.search([
                ('sale_order_id', '=', signed.sale_order_id.id),
                ('document_type', '=', 'delivery_note'),
            ], limit=1)
            if not nxt:
                invs = signed.sale_order_id.invoice_ids
                if invs:
                    nxt = Model.search([
                        ('move_id', 'in', invs.ids),
                        ('document_type', 'in', ('invoice', 'tax_invoice')),
                    ], limit=1)
        elif signed.document_type == 'delivery_note' and signed.sale_order_id:
            invs = signed.sale_order_id.invoice_ids
            nxt = None
            if invs:
                nxt = Model.search([
                    ('move_id', 'in', invs.ids),
                    ('document_type', 'in', ('invoice', 'tax_invoice')),
                ], limit=1)
        elif signed.document_type in ('invoice', 'tax_invoice') and signed.move_id:
            pays = signed.move_id.reconciled_payment_ids
            nxt = None
            if pays:
                nxt = Model.search([
                    ('payment_id', 'in', pays.ids),
                    ('document_type', 'in', ('payment_receipt', 'payment_slip')),
                ], limit=1)
        else:
            nxt = None
        return self._link_dict(nxt)

    @staticmethod
    def _verify_signature(signed):
        """Verify the stored detached RSA signature with the stored public key."""
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            from ..services.signing_service import SigningService

            pub = serialization.load_pem_public_key(signed.public_key_pem.encode())
            sig = base64.b64decode(signed.signature_b64)
            # Verify against the STORED attachment bytes (the exact PDF that was signed)
            stored = base64.b64decode(signed.signed_attachment_id.datas)
            pub.verify(sig, stored, padding.PKCS1v15(), hashes.SHA256())
            return True
        except Exception:
            return False
