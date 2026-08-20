/** @odoo-module **/

import { _t } from '@web/core/l10n/translation';
import { rpc, RPCError } from '@web/core/network/rpc';
import { patch } from '@web/core/utils/patch';

import { PaymentForm } from '@payment/interactions/payment_form';

patch(PaymentForm.prototype, {

    setup() {
        super.setup();
        this.omiseJS = null;
    },

    // #=== DOM MANIPULATION ===#

    /**
     * Prepare the inline form of Omise for direct payment.
     *
     * @override method from @payment/js/payment_form
     * @private
     * @param {number} providerId - The id of the selected payment option's provider.
     * @param {string} providerCode - The code of the selected payment option's provider.
     * @param {number} paymentOptionId - The id of the selected payment option
     * @param {string} paymentMethodCode - The code of the selected payment method, if any.
     * @param {string} flow - The online payment flow of the selected payment option.
     * @return {void}
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== 'omise') {
            await super._prepareInlineForm(...arguments);
            return;
        }
        if (flow === 'token') {
            return; // No elements for tokens.
        }
        this._setPaymentFlow('direct');
    },

    // #=== PAYMENT FLOW ===#

    /**
     * Process the direct payment flow for Omise.
     *
     * Card: create a token via Omise.js, then POST it to the token route.
     * PromptPay: create the source + charge, then show the QR inline.
     *
     * @override method from payment.payment_form
     * @private
     * @param {string} providerCode - The code of the selected payment option's provider.
     * @param {number} paymentOptionId - The id of the selected payment option.
     * @param {string} paymentMethodCode - The code of the selected payment method, if any.
     * @param {object} processingValues - The processing values of the transaction.
     * @return {void}
     */
    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'omise') {
            await super._processDirectFlow(...arguments);
            return;
        }

        try {
            if (paymentMethodCode === 'promptpay') {
                // PromptPay: create the source + charge, then go to the status
                // page — the custom omise_state_header shows the QR there.
                // (User instruction 2026-08-20: no inline QR in the PAY popup.)
                const result = await this.waitFor(rpc('/payment/omise/promptpay', {
                    'reference': processingValues.reference,
                }));
                if (result && result.error) {
                    this._displayErrorDialog(_t("Payment processing failed"), result.error);
                    this._enableButton();
                    return;
                }
                window.location = '/payment/status';
            } else {
                // Card: create a token via Omise.js, then charge it.
                const token = await this._omiseCreateToken(processingValues);
                if (!token) {
                    this._displayErrorDialog(_t("Payment processing failed"), _t("Could not create a card token. Please check your card details."));
                    this._enableButton();
                    return;
                }
                const result = await this.waitFor(rpc('/payment/omise/token', {
                    'reference': processingValues.reference,
                    'omise_token': token,
                }));
                if (result && result.error) {
                    this._displayErrorDialog(_t("Payment processing failed"), result.error);
                    this._enableButton();
                    return;
                }
                window.location = '/payment/status';
            }
        } catch (error) {
            if (error instanceof RPCError) {
                this._displayErrorDialog(_t("Payment processing failed"), error.data.message);
                this._enableButton();
            } else {
                return Promise.reject(error);
            }
        }
    },

    /**
     * Create a card token via Omise.js.
     *
     * @private
     * @param {object} processingValues - The processing values of the transaction.
     * @return {Promise<string|null>} The Omise token, or null on failure.
     */
    async _omiseCreateToken(processingValues) {
        const publishableKey = processingValues['omise_publishable_key'];
        if (!publishableKey) {
            return null;
        }
        // Load Omise.js on demand.
        if (!window.Omise) {
            await new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = 'https://cdn.omise.co/omise.js';
                script.onload = resolve;
                script.onerror = () => reject(new Error('Failed to load Omise.js'));
                document.head.appendChild(script);
            });
        }
        const Omise = window.Omise;
        Omise.setPublicKey(publishableKey);

        // Build the token parameters object from the card form fields.
        // Omise.js v2 expects an object, not a form element (v1 API).
        const cardForm = document.querySelector('[name="o_omise_card_form"]');
        if (!cardForm) {
            return null;
        }
        const getVal = (name) => {
            const input = cardForm.querySelector(`[name="${name}"]`);
            return input ? input.value.trim() : '';
        };
        const tokenParameters = {
            'name': getVal('card[name]'),
            'number': getVal('card[number]').replace(/\s+/g, ''),
            'expiration_month': getVal('card[expiration_month]'),
            'expiration_year': getVal('card[expiration_year]'),
            'security_code': getVal('card[security_code]'),
        };
        if (!tokenParameters.number || !tokenParameters.expiration_month
            || !tokenParameters.expiration_year || !tokenParameters.security_code) {
            return null;
        }

        return new Promise((resolve) => {
            Omise.createToken('card', tokenParameters, (statusCode, response) => {
                if (statusCode === 200 && response.id) {
                    resolve(response.id);
                } else {
                    resolve(null);
                }
            });
        });
    },

});
