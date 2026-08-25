from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _reconcile_payments(self, to_process, edit_mode=False):
        """After reconciliation, raise WHT reminders + certs for paid bills (VS-05).

        The withholding obligation is incurred at payment (มาตรา 50); the
        certificate must be issued "immediately" (มาตรา 50 ทวิ) and the
        withheld tax remitted with the monthly ภ.ง.ด.3/53 return by the
        7th of the following month (15th e-filing — the extension applies
        to the remittance because it is filed with the return per มาตรา 59).

        For every reconciled vendor bill carrying WHT tax lines, create a
        viva.wht.reminder (idempotent per payment+bill) and attach the
        generated WHT certificate PDF to the payment.
        """
        res = super()._reconcile_payments(to_process, edit_mode=edit_mode)
        for vals in to_process:
            payment = vals.get('payment')
            if not payment:
                continue
            bills = payment.reconciled_bill_ids.filtered(
                lambda b: b.line_ids.filtered(
                    lambda l: l.tax_line_id and l.tax_line_id.amount < 0)
                or self._missed_wht_bill(payment, b))
            for bill in bills:
                self.env['viva.wht.reminder']._create_for_payment(payment, bill)
        return res

    @api.model
    def _missed_wht_bill(self, payment, bill):
        """No-WHT bill that still needs a reminder (VS-08 missed-WHT case).

        The 1,000 THB de-minimis is cumulative per vendor per year: a bill
        without WHT lines still needs a reminder when the annual cumulative
        paid to the vendor exceeds 1,000 (the threshold was crossed).
        """
        partner = bill.commercial_partner_id
        if not partner or partner.viva_income_type == 'goods':
            return False
        return partner._cumulative_paid_year(payment.date.year) > 1000.0
