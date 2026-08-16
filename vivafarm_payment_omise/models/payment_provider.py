from odoo import fields, models

# The codes of the payment methods to activate when Omise is activated.
DEFAULT_PAYMENT_METHOD_CODES = {
    'card',
    'promptpay',
}


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('omise', "Omise")], ondelete={'omise': 'set default'})
    omise_publishable_key = fields.Char(
        string="Publishable Key",
        help="The key solely used to identify the account with Omise",
        required_if_provider='omise',
        copy=False,
    )
    omise_secret_key = fields.Char(
        string="Secret Key",
        required_if_provider='omise',
        copy=False,
        groups='base.group_system',
    )
    omise_webhook_secret = fields.Char(
        string="Webhook Signing Secret",
        help="If a webhook is enabled on your Omise account, this signing secret must be set to "
             "authenticate the messages sent from Omise to Odoo.",
        copy=False,
        groups='base.group_system',
    )

    # === COMPUTE METHODS === #

    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment methods for Omise. """
        if self.code != 'omise':
            return super()._get_default_payment_method_codes()
        return DEFAULT_PAYMENT_METHOD_CODES

    def _compute_feature_support_fields(self):
        """ Override of `payment` to enable additional features. """
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'omise').update({
            'support_manual_capture': False,
            'support_refund': 'partial',
            'support_tokenization': False,
        })
