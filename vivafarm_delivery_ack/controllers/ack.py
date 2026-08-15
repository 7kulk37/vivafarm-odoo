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
