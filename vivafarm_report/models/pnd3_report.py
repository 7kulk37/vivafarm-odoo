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
        income_lines = self._get_wht_lines(wizard, 'Income PND3')
        remit_lines = self._get_wht_lines(wizard, 'PND3')
        total_income = sum(l.tax_base_amount for l in income_lines)
        total_remit = sum(-l.balance for l in remit_lines)
        surcharge = 0.0
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
