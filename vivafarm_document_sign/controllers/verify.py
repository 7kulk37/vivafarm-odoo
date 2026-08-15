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
            'state': signed.state,
            'signed_at': signed.signed_at,
            'signer': signed.signer_user_id.name if signed.signer_user_id else '',
            'certificate_subject': signed.certificate_subject,
            'certificate_issuer': signed.certificate_issuer,
            'certificate_type': signed.certificate_type,
            'pdf_sha256': signed.pdf_sha256,
            'odoo_record_locked': True,  # signed => lock enforced at ORM level
        }

        # Signature verification (independent of upload — always shown)
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
