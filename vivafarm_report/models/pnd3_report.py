from odoo import api, models
from odoo.tools import format_amount
from odoo.tools.misc import format_date


class ReportPnd3(models.AbstractModel):
    """Data model for the ภ.ง.ด.3 (monthly WHT return — payments to individuals).

    Same statutory shape as PND53 but for PND3-tagged WHT taxes
    (1%/2%/3%/5% WH P * — payments to individuals).
    """

    _name = 'report.vivafarm_report.report_pnd3'
    _description = 'Thai PND3 (ภ.ง.ด.3) Data'

    @api.model
    def _get_wht_lines(self, wizard, tag_name):
        """Posted WHT lines whose bill was PAID in the selected period.

        The PND month is the month of PAYMENT (มาตรา 50 — withholding
        occurs at payment), not the invoice date. A bill invoiced in month
        A but paid in month B belongs in month B's return. Unpaid bills
        are excluded (no withholding yet).
        """
        lines = self.env['account.move.line'].search([
            ('parent_state', '=', 'posted'),
            ('tax_line_id', '!=', False),
            ('tax_line_id.amount', '<', 0),
            ('tax_line_id.invoice_repartition_line_ids.tag_ids.name', '=', tag_name),
        ])
        return lines.filtered(lambda l: self._bill_paid_in_period(l.move_id, wizard))

    @api.model
    def _bill_paid_in_period(self, bill, wizard):
        return bool(bill._get_reconciled_payments().filtered(
            lambda p: wizard.date_from <= p.date <= wizard.date_to))

    @api.model
    def _payment_date_in_period(self, bill, wizard):
        pay = bill._get_reconciled_payments().filtered(
            lambda p: wizard.date_from <= p.date <= wizard.date_to)
        return pay[:1].date if pay else False

    @api.model
    def _payment_ratio_in_period(self, bill, wizard):
        """Share of the bill paid in the wizard period (VS-10).

        Partial payments split WHT across months: each PND period reports
        only the WHT on the portion paid in that period. Returns 1.0 when
        the bill was fully paid in-period, 0.0 when nothing was paid
        in-period (caller filters those out anyway).
        """
        payments = bill._get_reconciled_payments()
        in_period = payments.filtered(
            lambda p: wizard.date_from <= p.date <= wizard.date_to)
        if not in_period:
            return 0.0
        total = sum(payments.mapped('amount'))
        if not total:
            return 1.0
        return sum(in_period.mapped('amount')) / total

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['tax.report.wizard'].browse(docids)
        currency = self.env.company.currency_id
        income_lines = self._get_wht_lines(wizard, 'Income PND3')
        remit_lines = self._get_wht_lines(wizard, 'PND3')
        total_income = 0.0
        total_remit = 0.0
        surcharge = 0.0
        rows = []
        for l in remit_lines:
            ratio = self._payment_ratio_in_period(l.move_id, wizard)
            pay_date = self._payment_date_in_period(l.move_id, wizard)
            income = l.tax_base_amount * ratio
            remit = -l.balance * ratio
            total_income += income
            total_remit += remit
            rows.append({
                'date': pay_date or l.date,
                'name': l.move_id.name,
                'partner': l.partner_id.name,
                'income': income,
                'remit': remit,
                'income_fmt': format_amount(self.env, income, currency),
                'remit_fmt': format_amount(self.env, remit, currency),
            })
        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'date_from': wizard.date_from,
            'date_to': wizard.date_to,
            # Thai Buddhist-Era dates for the period line: "01-ส.ค.-2569"
            'thai_date_from': '%s-%s' % (
                format_date(self.env, wizard.date_from, lang_code='th_TH', date_format='dd-MMM'),
                wizard.date_from.year + 543),
            'thai_date_to': '%s-%s' % (
                format_date(self.env, wizard.date_to, lang_code='th_TH', date_format='dd-MMM'),
                wizard.date_to.year + 543),
            'rows': rows,
            'total_income': format_amount(self.env, total_income, currency),
            'total_remit': format_amount(self.env, total_remit, currency),
            'surcharge': format_amount(self.env, surcharge, currency),
            'total': format_amount(self.env, total_remit + surcharge, currency),
        }
