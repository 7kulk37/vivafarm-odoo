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

        evidence = evidence_model.create({
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
        # Markup object instead (the documented way). The message links to
        # the evidence record and the uploaded file for one-click review.
        # Pending evidence gets Validate/Reject links (styled as buttons;
        # the sanitizer strips <button> tags, so we use <a> to controller
        # routes that flip the state and redirect back to the invoice).
        from markupsafe import Markup
        state_label = dict(evidence_model._fields['state'].selection).get(state, state)
        buttons = Markup('')
        if state == 'pending':
            buttons = Markup(
                ' <a href="/payment/evidence/validate/%d" class="btn btn-primary btn-sm">Validate</a>'
                ' <a href="/payment/evidence/reject/%d" class="btn btn-secondary btn-sm">Reject</a>'
            ) % (evidence.id, evidence.id)
        for invoice in tx.invoice_ids:
            invoice.message_post(
                body=Markup(
                    '<p>Payment evidence '
                    '<a href="#" data-oe-model="viva.payment.evidence" data-oe-id="%s">%s</a>: '
                    '<a href="/web/content/%s?download=true">%s</a> — <b>%s</b> (%s)%s</p>'
                ) % (evidence.id, evidence.name, attachment.id, filename, state_label, message, buttons),
                author_id=tx.partner_id.id,
            )

        _logger.info('Payment evidence uploaded for %s: %s (%s)', tx.reference, filename, state)
        return request.redirect('/payment/status')

    @http.route('/payment/evidence/validate/<int:evidence_id>', type='http', auth='user', methods=['GET'])
    def validate_evidence(self, evidence_id, **post):
        """Seller validates a pending evidence record, then returns to the invoice."""
        evidence = request.env['viva.payment.evidence'].browse(evidence_id).exists()
        if evidence and evidence.state == 'pending':
            evidence.action_validate()
            self._post_action_message(evidence, 'Validated')
        return self._redirect_to_invoice(evidence)

    @http.route('/payment/evidence/reject/<int:evidence_id>', type='http', auth='user', methods=['GET'])
    def reject_evidence(self, evidence_id, **post):
        """Seller rejects a pending evidence record, then returns to the invoice."""
        evidence = request.env['viva.payment.evidence'].browse(evidence_id).exists()
        if evidence and evidence.state == 'pending':
            evidence.action_reject()
            self._post_action_message(evidence, 'Rejected')
        return self._redirect_to_invoice(evidence)

    def _post_action_message(self, evidence, action_label):
        """Post a follow-up chatter note so the invoice log reflects the action."""
        from markupsafe import Markup
        for invoice in evidence.transaction_id.invoice_ids:
            invoice.message_post(
                body=Markup(
                    '<p>Payment evidence <a href="#" data-oe-model="viva.payment.evidence" '
                    'data-oe-id="%s">%s</a> — <b>%s</b> by %s</p>'
                ) % (evidence.id, evidence.name, action_label, request.env.user.name),
                author_id=request.env.user.partner_id.id,
            )

    def _redirect_to_invoice(self, evidence):
        """Redirect back to the invoice the evidence belongs to (or the list)."""
        if evidence and evidence.transaction_id.invoice_ids:
            invoice = evidence.transaction_id.invoice_ids[0]
            return request.redirect('/odoo/account.move/%d' % invoice.id)
        return request.redirect('/odoo/action-payment_evidence')

    def _get_monitored_transaction(self):
        """Mirror payment.post_processing._get_monitored_transaction."""
        tx_id = request.session.get('__payment_monitored_tx_id__')
        if not tx_id:
            return None
        return request.env['payment.transaction'].sudo().browse(tx_id).exists()
