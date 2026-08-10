from odoo import api, models
from odoo.tools import format_amount


class ReportPnd1(models.AbstractModel):
    """Data model for the ภ.ง.ด.1 (monthly PIT withholding — employees).

    Computes from posted wage payments (account.move lines on the Employee
    Benefit Obligations account 222100, i.e. the wage JEs the demo posts for
    Worker X / Worker Y). PIT withheld is 0 in the demo because weekly wages
    (~1,100 THB) are below the annual PIT threshold — the report structure
    is the deliverable; the accountant enters PIT when wages exceed it.
    """

    _name = 'report.vivafarm_report.report_pnd1'
    _description = 'Thai PND1 (ภ.ง.ด.1) Data'

    @api.model
    def _get_wage_lines(self, wizard):
        """Posted wage-payment lines in period (222100, payment moves)."""
        acc = self.env['account.account'].search(
            [('name', 'ilike', 'Employee Benefit Obligations')], limit=1)
        if not acc:
            return self.env['account.move.line']
        return self.env['account.move.line'].search([
            ('account_id', '=', acc.id),
            ('parent_state', '=', 'posted'),
            ('date', '>=', wizard.date_from),
            ('date', '<=', wizard.date_to),
            ('move_id.name', 'like', 'PBNK%'),
        ])

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['tax.report.wizard'].browse(docids)
        currency = self.env.company.currency_id
        lines = self._get_wage_lines(wizard)
        total_wages = sum(l.balance for l in lines)
        total_pit = 0.0  # demo wages below PIT threshold
        rows = []
        for l in lines:
            rows.append({
                'date': l.date,
                'name': l.move_id.name,
                'employee': l.name.split(':')[0].strip() if ':' in l.name else l.name,
                'wages': l.balance,
                'wages_fmt': format_amount(self.env, l.balance, currency),
                'pit_fmt': format_amount(self.env, 0.0, currency),
            })
        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'date_from': wizard.date_from,
            'date_to': wizard.date_to,
            'rows': rows,
            'total_wages': format_amount(self.env, total_wages, currency),
            'total_pit': format_amount(self.env, total_pit, currency),
            'total': format_amount(self.env, total_pit, currency),
        }
