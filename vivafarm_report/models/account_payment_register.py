from odoo import models


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
                    lambda l: l.tax_line_id and l.tax_line_id.amount < 0))
            for bill in bills:
                self.env['viva.wht.reminder']._create_for_payment(payment, bill)
        return res
