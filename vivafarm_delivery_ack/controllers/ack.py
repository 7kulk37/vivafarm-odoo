"""Public delivery acknowledgment — GET/POST /ack/<token>.

NO Odoo login required (same trust model as the /v/<token> verify page):
the customer opens the link from the delivery-confirmation email, types
their name (and optionally draws a signature), and clicks "I confirm
receipt". Evidence (name, signature, timestamp, IP, user agent) is
appended to the immutable audit table.

The page never exposes record IDs or internal fields beyond the evidence.
"""
import base64
import binascii
import logging

from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

_logger = logging.getLogger(__name__)


class VivaDeliveryAckController(http.Controller):

    @http.route('/ack/<token>', type='http', auth='public', website=True,
                csrf=False, methods=['GET', 'POST'])
    def ack(self, token, **kwargs):
        """Render the confirmation page; POST records the acknowledgment."""
        ack = request.env['viva.delivery.ack'].sudo().search(
            [('ack_token', '=', token)], limit=1)
        if not ack:
            return request.not_found()

        if request.httprequest.method == 'POST':
            name = kwargs.get('name', '')
            signature = kwargs.get('signature', '')
            if not name.strip():
                return request.render('vivafarm_delivery_ack.ack_page', {
                    'ack': ack,
                    'error': _('Please enter your name.'),
                })
            try:
                if signature:
                    base64.b64decode(signature, validate=True)
            except (TypeError, binascii.Error):
                return request.render('vivafarm_delivery_ack.ack_page', {
                    'ack': ack,
                    'error': _('Invalid signature data.'),
                })

            ack.action_confirm(
                customer_name=name,
                signature_b64=signature or False,
                ip=request.httprequest.remote_addr or '',
                user_agent=request.httprequest.user_agent or '',
            )
            return request.render('vivafarm_delivery_ack.ack_confirmed', {
                'ack': ack,
            })

        return request.render('vivafarm_delivery_ack.ack_page', {
            'ack': ack,
            'error': False,
        })

    @http.route('/ack/<token>/confirm', type='json', auth='public', website=True,
                csrf=False, methods=['POST'])
    def ack_confirm(self, token, **kwargs):
        """JSON-RPC endpoint for the signature_form component.

        The portal.signature_form component does its own rpc() call to
        call_url with {name, signature} and expects a JSON response with
        force_refresh / error. This mirrors the sale portal's
        /my/orders/<id>/accept route.
        """
        ack = request.env['viva.delivery.ack'].sudo().search(
            [('ack_token', '=', token)], limit=1)
        if not ack:
            return {'error': _('Invalid link.')}
        if ack.state != 'pending':
            return {'force_refresh': True}

        name = kwargs.get('name', '')
        signature = kwargs.get('signature', '')
        if not name.strip():
            return {'error': _('Please enter your name.')}
        try:
            if signature:
                base64.b64decode(signature, validate=True)
        except (TypeError, binascii.Error):
            return {'error': _('Invalid signature data.')}

        ack.action_confirm(
            customer_name=name,
            signature_b64=signature or False,
            ip=request.httprequest.remote_addr or '',
            user_agent=request.httprequest.user_agent or '',
        )
        return {'force_refresh': True}

    @http.route('/ack/<token>/pdf', type='http', auth='public', website=True,
                csrf=False, methods=['GET'])
    def ack_pdf(self, token, **kwargs):
        """Serve the delivery-note PDF (no login, token-scoped)."""
        ack = request.env['viva.delivery.ack'].sudo().search(
            [('ack_token', '=', token)], limit=1)
        if not ack:
            return request.not_found()
        pdf = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'vivafarm_report.viva_delivery_note', [ack.picking_id.id])[0]
        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition',
                 'inline; filename="%s.pdf"' % ack.document_number),
            ],
        )
