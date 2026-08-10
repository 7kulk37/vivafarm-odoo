from odoo import api, models
from odoo.tools import format_amount


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
        """Posted WHT lines in period carrying the given tag."""
        return self.env['account.move.line'].search([
            ('parent_state', '=', 'posted'),
            ('tax_line_id', '!=', False),
            ('tax_line_id.amount', '<', 0),
            ('date', '>=', wizard.date_from),
            ('date', '<=', wizard.date_to),
            ('tax_line_id.invoice_repartition_line_ids.tag_ids.name', '=', tag_name),
        ])

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
            rows.append({
                'date': l.date,
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
            'rows': rows,
            'total_income': format_amount(self.env, total_income, currency),
            'total_remit': format_amount(self.env, total_remit, currency),
            'surcharge': format_amount(self.env, surcharge, currency),
            'total': format_amount(self.env, total_remit + surcharge, currency),
        }
