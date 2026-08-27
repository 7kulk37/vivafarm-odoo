"""Public archived-copy proof — GET/POST /pl/<token>.

NO Odoo login required (auditors/customers). Shows that the signed
document was archived into Paperless-ngx: Paperless doc id + link,
uploaded-at timestamp, the SHA-256 of the exact bytes uploaded, and the
current archive state. POST re-verifies by downloading the archived copy
back and running the semantic check (valid PDF + document number in text
— Paperless rewrites born-digital PDFs during OCR, so byte-identity is
impossible by design; the uploaded-bytes hash is the Odoo-side proof).

Reuses the sign module's verification_token — the same token that already
rides in the QR / verify page.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PaperlessProofController(http.Controller):

    @http.route('/pl/<token>', type='http', auth='public', website=False,
                csrf=False, methods=['GET', 'POST'])
    def proof(self, token, **kwargs):
        signed = request.env['viva.signed.document'].sudo().search(
            [('verification_token', '=', token)], limit=1)
        if not signed:
            return request.not_found()

        result = {
            'document_number': signed.document_number,
            'document_type': signed.document_type,
            'verification_code': signed.verification_code,
            'verification_token': signed.verification_token,
            'state': signed.state,
            'signed_at': signed.signed_at,
            'paperless_document_id': signed.paperless_document_id,
            'paperless_upload_state': signed.paperless_upload_state,
            'paperless_title': signed.paperless_title,
            'paperless_uploaded_at': signed.paperless_uploaded_at,
            'paperless_sha256_of_uploaded': signed.paperless_sha256_of_uploaded,
            'paperless_last_verified_at': signed.paperless_last_verified_at,
            'paperless_upload_error': signed.paperless_upload_error,
            'paperless_doc_url': signed.paperless_doc_url,
            'reverify_result': None,
        }

        if request.httprequest.method == 'POST' and signed.paperless_document_id:
            try:
                ok = signed._paperless_verify()
                result['reverify_result'] = {
                    'ok': ok,
                    'state': signed.paperless_upload_state,
                    'error': signed.paperless_upload_error,
                    'last_verified_at': signed.paperless_last_verified_at,
                }
                # Re-read after the verify write
                result['paperless_upload_state'] = signed.paperless_upload_state
                result['paperless_last_verified_at'] = signed.paperless_last_verified_at
                result['paperless_upload_error'] = signed.paperless_upload_error
            except Exception as e:
                result['reverify_result'] = {
                    'ok': False,
                    'state': 'error',
                    'error': str(e)[:300],
                    'last_verified_at': signed.paperless_last_verified_at,
                }

        return request.render('vivafarm_paperless_archive.paperless_proof_page',
                              result)
