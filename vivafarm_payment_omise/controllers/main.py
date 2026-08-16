import logging

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class OmiseController(http.Controller):
    _return_url = '/payment/omise/return'
    _token_url = '/payment/omise/token'

    @http.route(_return_url, type='http', methods=['GET'], auth='public')
    def omise_return(self, **data):
        """ Process the payment data sent by Omise after the customer returns.

        :param dict data: The payment data, including the reference.
        """
        tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference('omise', data)
        if tx_sudo:
            # Fetch the charge from Omise to get the authoritative status.
            try:
                charge = tx_sudo._omise_request('GET', f"charges/{tx_sudo.provider_reference}")
            except ValidationError:
                _logger.error("Failed to fetch Omise charge for %s", tx_sudo.reference)
            else:
                tx_sudo._process('omise', {'reference': tx_sudo.reference, 'omise_charge': charge})

        return request.redirect('/payment/status')

    @http.route(_token_url, type='jsonrpc', auth='public')
    def omise_token(self, **data):
        """ Process the Omise token created by the customer's browser.

        :param dict data: The payment data, including the token and reference.
        """
        reference = data.get('reference')
        token = data.get('omise_token')
        if not reference or not token:
            return {'error': 'Missing reference or token'}

        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'omise'),
        ], limit=1)
        if not tx_sudo:
            return {'error': 'No transaction found'}

        try:
            charge = tx_sudo._omise_create_charge(token)
        except ValidationError as error:
            return {'error': str(error)}

        if not charge:
            return {'error': 'Charge creation failed'}

        tx_sudo._process('omise', {'reference': reference, 'omise_charge': charge})
        return {'charge_id': charge.get('id'), 'status': charge.get('status')}
