import base64
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PaymentEvidenceController(http.Controller):

    @http.route('/payment/evidence/upload', type='http', auth='public', methods=['POST'], csrf=False)
    def upload_evidence(self, **post):
        """Handle the evidence upload from the Wire Transfer payment status page.

        The status page is session-bound (the transaction id lives in the
        session), so we resolve the transaction the same way the payment
        module does: from the session, falling back to the posted reference.
        """
        tx = self._get_monitored_transaction()
        if not tx:
            ref = post.get('reference', '')
            tx = request.env['payment.transaction'].sudo().search(
                [('reference', '=', ref)], limit=1)
        if not tx:
            return request.redirect('/payment/status')

        evidence_model = request.env['viva.payment.evidence'].sudo()
        check_model = request.env['viva.payment.evidence.check'].sudo()

        upload = post.get('evidence_file')
        if not upload:
            return request.redirect('/payment/status')

        filename = upload.filename or 'evidence'
        mimetype = upload.content_type or 'application/octet-stream'
        data = upload.read()

        state, message = check_model._check(tx, filename, mimetype, data)

        attachment = request.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'mimetype': mimetype,
            'raw': data,
            'res_model': 'viva.payment.evidence',
        })

        evidence_model.create({
            'name': '%s-%s' % (tx.reference or 'tx', tx.id),
            'transaction_id': tx.id,
            'partner_id': tx.partner_id.id,
            'amount': tx.amount,
            'currency_id': tx.currency_id.id,
            'state': state,
            'filename': filename,
            'mimetype': mimetype,
            'file_size': len(data),
            'attachment_id': attachment.id,
            'check_result': message,
        })

        # Post a chatter message on the linked invoice(s) so the seller sees
        # the upload right in the invoice log. Odoo 19 escapes plain str
        # bodies and body_is_html only works for internal users — use a
        # Markup object instead (the documented way).
        from markupsafe import Markup
        state_label = dict(evidence_model._fields['state'].selection).get(state, state)
        for invoice in tx.invoice_ids:
            invoice.message_post(
                body=Markup(
                    '<p>Customer uploaded payment evidence: <b>%s</b> '
                    '(%s — %s)</p>'
                ) % (filename, state_label, message),
                author_id=tx.partner_id.id,
            )

        _logger.info('Payment evidence uploaded for %s: %s (%s)', tx.reference, filename, state)
        return request.redirect('/payment/status')

    def _get_monitored_transaction(self):
        """Mirror payment.post_processing._get_monitored_transaction."""
        tx_id = request.session.get('__payment_monitored_tx_id__')
        if not tx_id:
            return None
        return request.env['payment.transaction'].sudo().browse(tx_id).exists()
