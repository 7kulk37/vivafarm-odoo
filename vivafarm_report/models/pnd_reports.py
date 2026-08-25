from odoo import api, models
from odoo.tools import format_amount
from odoo.tools.misc import format_date


class ReportPnd53(models.AbstractModel):
    """Data model for the ภ.ง.ด.53 (monthly WHT return — payments to companies).

    Computes the statutory lines from posted WHT tax lines tagged PND53 in
    the selected period (same tags the official l10n_th PND53 account report
    uses, so numbers agree with the CSV export):
      - Total Income (รวมยอดเงินได้ทั้งสิ้น)  = sum of WHT tax bases
      - Total Remittance (รวมยอดภาษีที่นำส่ง) = sum of withheld amounts
      - Surcharge (เงินเพิ่ม)                 = 0 (no late filing in demo)
      - Total (รวม)                          = remittance + surcharge
    """

    _name = 'report.vivafarm_report.report_pnd53'
    _description = 'Thai PND53 (ภ.ง.ด.53) Data'

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
    def _get_report_values(self, docids, data=None):
        wizard = self.env['tax.report.wizard'].browse(docids)
        currency = self.env.company.currency_id
        income_lines = self._get_wht_lines(wizard, 'Income PND53')
        remit_lines = self._get_wht_lines(wizard, 'PND53')
        total_income = sum(l.tax_base_amount for l in income_lines)
        total_remit = sum(-l.balance for l in remit_lines)
        surcharge = 0.0
        # Detail rows per partner for the register section
        rows = []
        for l in remit_lines:
            pay_date = self._payment_date_in_period(l.move_id, wizard)
            rows.append({
                'date': pay_date or l.date,
                'name': l.move_id.name,
                'partner': l.partner_id.name,
                'income': l.tax_base_amount,
                'remit': -l.balance,
                'income_fmt': format_amount(self.env, l.tax_base_amount, currency),
                'remit_fmt': format_amount(self.env, -l.balance, currency),
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
