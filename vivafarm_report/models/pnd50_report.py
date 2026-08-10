from odoo import api, models
from odoo.tools import format_amount


class ReportPnd50(models.AbstractModel):
    """Data model for the ภ.ง.ด.50 (annual corporate income tax return).

    Computes the statutory summary from the trial balance in the selected
    period: revenue, expenses, net profit, CIT at 20% (standard rate).
    The full ภ.ง.ด.50 form (with tax adjustments) is accountant-prepared;
    this report gives the accountant the numbers from Odoo.
    """

    _name = 'report.vivafarm_report.report_pnd50'
    _description = 'Thai PND50 (ภ.ง.ด.50) Data'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['tax.report.wizard'].browse(docids)
        currency = self.env.company.currency_id
        # Trial balance in period
        lines = self.env['account.move.line'].search([
            ('parent_state', '=', 'posted'),
            ('date', '>=', wizard.date_from),
            ('date', '<=', wizard.date_to),
        ])
        revenue = 0.0
        expenses = 0.0
        for l in lines:
            if l.account_id.account_type in ('income', 'other_income'):
                revenue += -l.balance  # income accounts are credit-natured
            elif l.account_id.account_type in ('expense', 'other_expense'):
                expenses += l.balance  # expense accounts are debit-natured
        net_profit = revenue - expenses
        tax_rate = 0.20
        tax = max(net_profit, 0.0) * tax_rate
        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'date_from': wizard.date_from,
            'date_to': wizard.date_to,
            'revenue': format_amount(self.env, revenue, currency),
            'expenses': format_amount(self.env, expenses, currency),
            'net_profit': format_amount(self.env, net_profit, currency),
            'tax_rate': tax_rate,
            'tax': format_amount(self.env, tax, currency),
        }


class ReportPnd51(models.AbstractModel):
    """Data model for the ภ.ง.ด.51 (half-year corporate income tax return).

    Same computation as PND50 but for the first half of the fiscal year.
    """

    _name = 'report.vivafarm_report.report_pnd51'
    _description = 'Thai PND51 (ภ.ง.ด.51) Data'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['tax.report.wizard'].browse(docids)
        currency = self.env.company.currency_id
        lines = self.env['account.move.line'].search([
            ('parent_state', '=', 'posted'),
            ('date', '>=', wizard.date_from),
            ('date', '<=', wizard.date_to),
        ])
        revenue = 0.0
        expenses = 0.0
        for l in lines:
            if l.account_id.account_type in ('income', 'other_income'):
                revenue += -l.balance
            elif l.account_id.account_type in ('expense', 'other_expense'):
                expenses += l.balance
        net_profit = revenue - expenses
        tax_rate = 0.20
        tax = max(net_profit, 0.0) * tax_rate
        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'date_from': wizard.date_from,
            'date_to': wizard.date_to,
            'revenue': format_amount(self.env, revenue, currency),
            'expenses': format_amount(self.env, expenses, currency),
            'net_profit': format_amount(self.env, net_profit, currency),
            'tax_rate': tax_rate,
            'tax': format_amount(self.env, tax, currency),
        }
