import logging

import requests

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_round
from odoo.tools.urls import urljoin as url_join

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.vivafarm_payment_omise.controllers.main import OmiseController

_logger = get_payment_logger(__name__)

# Omise API endpoints
OMISE_API_URL = 'https://api.omise.co/'
OMISE_VAULT_URL = 'https://vault.omise.co/'


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    omise_qr_url = fields.Char(
        string="Omise QR URL",
        help="The URL of the PromptPay QR code document for this transaction",
        copy=False,
    )

    # === COMPUTE METHODS === #

    def _get_specific_processing_values(self, processing_values):
        """ Override of `payment` to return Omise-specific processing values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic processing values of the transaction
        :return: The dict of provider-specific processing values
        :rtype: dict
        """
        if self.provider_code != 'omise':
            return super()._get_specific_processing_values(processing_values)

        base_url = self.provider_id.get_base_url()
        return {
            'omise_publishable_key': self.provider_id.omise_publishable_key,
            'omise_token': '',
            'return_url': url_join(
                base_url,
                f'{OmiseController._return_url}?reference={self.reference}',
            ),
        }

    def _send_payment_request(self):
        """ Override of `payment` to send a payment request to Omise.

        The customer's browser creates a token via Omise.js (vault.omise.co) using the
        publishable key, then POSTs it to the controller which calls this method.

        Note: self.ensure_one() from `_charge_with_token`
        """
        if self.provider_code != 'omise':
            return super()._send_payment_request()

        token = self._context.get('omise_token')
        if not token:
            raise ValidationError(_("Missing Omise token."))

        charge = self._omise_create_charge(token)
        if not charge:
            return  # The transaction is in error at this point.

        payment_data = {
            'reference': self.reference,
            'omise_charge': charge,
        }
        self._process('omise', payment_data)

    # === API METHODS === #

    def _omise_create_charge(self, token):
        """ Create a charge on Omise for this transaction.

        :param str token: The Omise token created by the customer's browser
        :return: The created charge object or None if creation failed
        :rtype: dict|None
        """
        try:
            response = self._omise_request(
                'POST',
                'charges',
                data={
                    'amount': self._omise_amount_in_satang(),
                    'currency': self.currency_id.name.lower(),
                    'card': token,
                    'description': self.reference,
                },
            )
        except ValidationError as error:
            self._set_error(str(error))
            return None
        else:
            return response

    def _omise_create_promptpay_source(self):
        """ Create a PromptPay source on Omise for this transaction.

        :return: The created source object
        :rtype: dict
        """
        return self._omise_request(
            'POST',
            'sources',
            data={
                'type': 'promptpay',
                'amount': self._omise_amount_in_satang(),
                'currency': self.currency_id.name.lower(),
            },
        )

    def _omise_create_promptpay_charge(self, source_id):
        """ Create a PromptPay charge on Omise for this transaction.

        The charge is created with a PromptPay source, which makes Omise
        generate a QR code document the customer scans with their bank app.

        :param str source_id: The Omise source id (type='promptpay')
        :return: The created charge object or None if creation failed
        :rtype: dict|None
        """
        try:
            response = self._omise_request(
                'POST',
                'charges',
                data={
                    'amount': self._omise_amount_in_satang(),
                    'currency': self.currency_id.name.lower(),
                    'source': source_id,
                    'description': self.reference,
                },
            )
        except ValidationError as error:
            self._set_error(str(error))
            return None
        else:
            return response

    def _omise_amount_in_satang(self):
        """ Convert the transaction amount to satang (1 THB = 100 satang). """
        return int(round(self.amount * 100))

    def _omise_request(self, method, endpoint, data=None):
        """ Send a request to the Omise API.

        :param str method: The HTTP method ('GET', 'POST', 'PATCH', 'DELETE')
        :param str endpoint: The API endpoint (e.g. 'charges')
        :param dict data: The request payload
        :return: The JSON response
        :rtype: dict
        """
        secret_key = self.provider_id.omise_secret_key
        if not secret_key:
            raise ValidationError(_("Omise secret key is not configured."))

        url = OMISE_API_URL + endpoint
        auth = (secret_key, '')
        try:
            response = requests.request(method, url, auth=auth, data=data, timeout=30)
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            _logger.error("Omise API error: %s", error)
            try:
                error_data = response.json()
                message = error_data.get('message', str(error))
            except Exception:
                message = str(error)
            raise ValidationError(_("Omise error: %s", message))
        except requests.exceptions.RequestException as error:
            _logger.error("Omise network error: %s", error)
            raise ValidationError(_("Omise network error: %s", str(error)))

        return response.json()

    # === PROCESSING METHODS === #

    def _omise_process_webhook_event(self, event):
        """ Process a webhook event received from Omise (model-level, testable).

        For charge.complete, fetch the charge independently (event verification)
        and process it — this sets the transaction to done, and the post-processing
        cron creates the payment and reconciles the invoice.

        :param dict event: The Omise event object
        :return: None
        """
        event_key = event.get('key')
        if event_key != 'charge.complete':
            _logger.info("Ignoring Omise webhook event: %s", event_key)
            return

        charge_id = (event.get('data') or {}).get('id')
        if not charge_id:
            _logger.warning("Omise webhook event missing charge id")
            return

        # Find the transaction by provider reference (the charge id).
        tx = self.search([
            ('provider_code', '=', 'omise'),
            ('provider_reference', '=', charge_id),
        ], limit=1)
        if not tx:
            _logger.warning("No Omise transaction found for charge %s", charge_id)
            return

        # Fetch the charge independently to verify its status (event verification).
        try:
            charge = tx._omise_request('GET', f"charges/{charge_id}")
        except ValidationError as error:
            _logger.error("Failed to fetch Omise charge %s: %s", charge_id, error)
            return

        tx._process('omise', {'reference': tx.reference, 'omise_charge': charge})

        # Post-process synchronously so the payment is created the moment the
        # webhook lands (no waiting for the cron). The cron remains as the
        # safety net for missed webhooks.
        if not tx.is_post_processed:
            tx._post_process()

    def _apply_updates(self, payment_data):
        """ Override of `payment` to update the transaction based on the Omise charge. """
        super()._apply_updates(payment_data)
        if self.provider_code != 'omise':
            return

        charge = payment_data.get('omise_charge')
        if not charge:
            return

        # Store the Omise charge reference
        self.provider_reference = charge.get('id')

        # Store the PromptPay QR URL (the customer scans this to pay).
        # The QR lives on the source's scannable_code.image.download_uri.
        source = charge.get('source') or {}
        scannable = source.get('scannable_code') or {}
        image = scannable.get('image') or {}
        if image.get('download_uri'):
            self.omise_qr_url = image['download_uri']

        status = charge.get('status')
        if status == 'successful':
            self._set_done()
        elif status == 'pending':
            self._set_pending()
        elif status == 'failed':
            failure_message = charge.get('failure_message') or charge.get('failure_code') or 'Payment failed'
            self._set_error(failure_message)
        else:
            self._set_error(f"Unknown Omise charge status: {status}")

    def _extract_amount_data(self, payment_data):
        """ Override of `payment` to extract the amount from the Omise charge. """
        if self.provider_code != 'omise':
            return super()._extract_amount_data(payment_data)

        charge = payment_data.get('omise_charge')
        if not charge:
            return None

        return {
            'amount': charge.get('amount', 0) / 100.0,
            'currency_code': charge.get('currency', '').upper(),
        }
