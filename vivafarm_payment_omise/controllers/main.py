import base64
import hashlib
import hmac
import logging

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class OmiseController(http.Controller):
    _return_url = '/payment/omise/return'
    _token_url = '/payment/omise/token'
    _webhook_url = '/payment/omise/webhook'

    # === WEBHOOK === #

    @http.route(_webhook_url, type='http', methods=['POST'], auth='public', csrf=False)
    def omise_webhook(self):
        """ Process the payment data sent by Omise to the webhook.

        :return: An empty string to acknowledge the notification.
        :rtype: str
        """
        raw_body = request.httprequest.get_data()
        event = request.get_json_data()
        _logger.info("Notification received from Omise: %s", event.get('key'))

        # Verify the signature (HMAC-SHA256, base64-encoded secret).
        signature = request.httprequest.headers.get('Omise-Signature', '')
        timestamp = request.httprequest.headers.get('Omise-Signature-Timestamp', '')
        if not self._verify_webhook_signature(signature, timestamp, raw_body):
            _logger.warning("Omise webhook signature verification failed")
            raise Forbidden()

        self._process_webhook_event(event)
        return request.make_response('')

    def _verify_webhook_signature(self, signature, timestamp, raw_body):
        """ Verify the HMAC-SHA256 signature of the webhook payload.

        Per Omise docs: signed payload = "{timestamp}.{raw_body}", the webhook
        secret is Base64-encoded and must be decoded before computing the HMAC.

        :param str signature: The value of the Omise-Signature header
        :param str timestamp: The value of the Omise-Signature-Timestamp header
        :param bytes raw_body: The raw webhook request body
        :return: True if the signature matches, False otherwise
        :rtype: bool
        """
        secret = request.env['payment.provider'].sudo().search(
            [('code', '=', 'omise')], limit=1
        ).omise_webhook_secret
        if not secret:
            _logger.warning("Omise webhook secret is not configured")
            return False

        return self._verify_webhook_signature_with_secret(secret, signature, timestamp, raw_body)

    @staticmethod
    def _verify_webhook_signature_with_secret(secret, signature, timestamp, raw_body):
        """ Pure signature check (testable without an HTTP request).

        :param str secret: The base64-encoded webhook secret
        :param str signature: The value of the Omise-Signature header
        :param str timestamp: The value of the Omise-Signature-Timestamp header
        :param bytes raw_body: The raw webhook request body
        :return: True if the signature matches, False otherwise
        :rtype: bool
        """
        try:
            decoded_secret = base64.b64decode(secret)
        except Exception:
            return False

        signed_payload = f"{timestamp}.".encode() + raw_body
        expected = hmac.new(decoded_secret, signed_payload, hashlib.sha256).hexdigest()

        # The header may contain multiple comma-separated signatures during rotation.
        for sig in signature.split(','):
            if hmac.compare_digest(sig.strip(), expected):
                return True
        return False

    def _process_webhook_event(self, event):
        """ Process a webhook event received from Omise.

        Delegates to the model-level method (testable in shell).

        :param dict event: The Omise event object
        :return: None
        """
        request.env['payment.transaction'].sudo()._omise_process_webhook_event(event)

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

    # === TOKEN === #

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

    # === PROMPTPAY === #

    @http.route('/payment/omise/promptpay', type='jsonrpc', auth='public')
    def omise_promptpay(self, **data):
        """ Create a PromptPay source + charge for the transaction.

        The customer's browser calls this after selecting PromptPay. The charge
        is created with a PromptPay source, which makes Omise generate a QR code
        the customer scans with their bank app.

        :param dict data: The payment data, including the reference.
        """
        reference = data.get('reference')
        if not reference:
            return {'error': 'Missing reference'}

        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'omise'),
        ], limit=1)
        if not tx_sudo:
            return {'error': 'No transaction found'}

        try:
            source = tx_sudo._omise_create_promptpay_source()
            charge = tx_sudo._omise_create_promptpay_charge(source['id'])
        except ValidationError as error:
            return {'error': str(error)}

        if not charge:
            return {'error': 'Charge creation failed'}

        tx_sudo._process('omise', {'reference': reference, 'omise_charge': charge})
        return {'charge_id': charge.get('id'), 'status': charge.get('status')}
