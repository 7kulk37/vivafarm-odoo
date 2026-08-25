from datetime import timedelta

from odoo import api, models
from odoo.tools import format_amount
from odoo.tools.misc import format_date


class ReportPnd1(models.AbstractModel):
    """Data model for the ภ.ง.ด.1 (monthly PIT withholding — employees).

    Computes from posted wage payments (account.move lines on the Employee
    Benefit Obligations account 222100, i.e. the wage JEs the demo posts for
    Worker X / Worker Y). PIT is computed with the CUMULATIVE year-to-date
    progressive method (VS-13c): tax on cumulative YTD income minus tax
    already withheld YTD = the month's withholding. The ≤150,000 THB annual
    band is auto-zero (0% rate); an employee crossing 150k mid-year starts
    withholding in the crossing month. The same report with a full-year
    period serves as the PND 1 Kor (ภ.ง.ด.1ก) year-end summary.
    """

    _name = 'report.vivafarm_report.report_pnd1'
    _description = 'Thai PND1 (ภ.ง.ด.1) Data'

    #: Progressive PIT brackets (2026): 0% ≤150k, then 5/10/15/20/25/30/35%.
    PIT_BRACKETS = [
        (150000, 0.00),
        (300000, 0.05),
        (500000, 0.10),
        (750000, 0.15),
        (1000000, 0.20),
        (2000000, 0.25),
        (5000000, 0.30),
        (float('inf'), 0.35),
    ]

    @api.model
    def _compute_pit(self, annual_income):
        """Progressive PIT on annual income (2026 table)."""
        tax = 0.0
        prev = 0
        for limit, rate in self.PIT_BRACKETS:
            if annual_income <= prev:
                break
            taxable = min(annual_income, limit) - prev
            tax += taxable * rate
            prev = limit
            if annual_income <= limit:
                break
        return tax

    @api.model
    def _get_wage_lines(self, wizard):
        """Posted wage-payment lines in period (222100, bank-journal moves)."""
        acc = self.env['account.account'].search(
            [('name', 'ilike', 'Employee Benefit Obligations')], limit=1)
        if not acc:
            return self.env['account.move.line']
        bank_journals = self.env['account.journal'].search(
            [('type', '=', 'bank')]).ids
        return self.env['account.move.line'].search([
            ('account_id', '=', acc.id),
            ('parent_state', '=', 'posted'),
            ('date', '>=', wizard.date_from),
            ('date', '<=', wizard.date_to),
            ('journal_id', 'in', bank_journals),
        ])

    @api.model
    def _employee_name(self, line):
        return line.name.split(':')[0].strip() if ':' in line.name else line.name

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['tax.report.wizard'].browse(docids)
        currency = self.env.company.currency_id
        lines = self._get_wage_lines(wizard)
        # Cumulative YTD: from Jan 1 of the period year through period end.
        ytd_from = wizard.date_to.replace(month=1, day=1)
        ytd_to = wizard.date_to
        acc = self.env['account.account'].search(
            [('name', 'ilike', 'Employee Benefit Obligations')], limit=1)
        bank_journals = self.env['account.journal'].search(
            [('type', '=', 'bank')]).ids
        ytd_lines = self.env['account.move.line'].search([
            ('account_id', '=', acc.id),
            ('parent_state', '=', 'posted'),
            ('date', '>=', ytd_from),
            ('date', '<=', ytd_to),
            ('journal_id', 'in', bank_journals),
        ]) if acc else self.env['account.move.line']
        # Per-employee sorted YTD payments (date, amount).
        emp_payments = {}
        for l in ytd_lines:
            name = self._employee_name(l)
            emp_payments.setdefault(name, []).append((l.date, l.balance))
        # Rows: per wage line in the period, with the month's PIT.
        # Cumulative method per PAYMENT: pit = tax(cumulative through this
        # payment) - tax(cumulative before this payment). Summing per-line
        # tax(YTD end) - tax(YTD start) would double-count.
        total_wages = 0.0
        total_pit = 0.0
        rows = []
        for l in lines:
            name = self._employee_name(l)
            payments = emp_payments.get(name, [])
            ytd_through = sum(amt for d, amt in payments if d <= l.date)
            ytd_before = sum(amt for d, amt in payments if d < l.date)
            pit = self._compute_pit(ytd_through) - self._compute_pit(ytd_before)
            total_wages += l.balance
            total_pit += pit
            rows.append({
                'date': l.date,
                'name': l.move_id.name,
                'employee': name,
                'wages': l.balance,
                'wages_fmt': format_amount(self.env, l.balance, currency),
                'pit': pit,
                'pit_fmt': format_amount(self.env, pit, currency),
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
            'total_wages': format_amount(self.env, total_wages, currency),
            'total_pit': format_amount(self.env, total_pit, currency),
            'total': format_amount(self.env, total_pit, currency),
        }
