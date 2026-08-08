from datetime import timedelta

from odoo import api, models


class ReportWageSlip(models.AbstractModel):
    """Data model for the Wage Slip / Pay Slip report (Labor Law 76).

    Per-worker-week report bound to ``hr.expense`` (the demo creates one
    paid expense per worker per 7-day week, e.g. "Worker X - Week 52",
    total = sum of that week's ``farm.worker.log`` wage_amount).

    Aggregates the worker's daily log rows for the 7-day window ending on
    the expense date (matching the demo's week-bucket semantics) and
    cross-checks the sum against the expense total.
    """

    _name = 'report.vivafarm_gap_reports.report_wage_slip'
    _description = 'Wage Slip Report Data'

    @api.model
    def _get_report_values(self, docids, data=None):
        expenses = self.env['hr.expense'].browse(docids).exists()
        rows = []
        for exp in expenses:
            worker_name = exp.employee_id.name or ''
            week_start = exp.date - timedelta(days=6)
            logs = self.env['farm.worker.log'].search([
                ('worker_name', '=', worker_name),
                ('date', '>=', week_start),
                ('date', '<=', exp.date),
            ], order='date')
            log_rows = [{
                'date': log.date,
                'task': log.task_description or '',
                'hours': log.working_hours or 0.0,
                'wage': log.wage_amount or 0.0,
            } for log in logs]
            total_hours = sum(r['hours'] for r in log_rows)
            total_wage = sum(r['wage'] for r in log_rows)
            rows.append({
                'expense': exp,
                'worker': worker_name,
                'period': exp.name or '',
                'payment_date': exp.date,
                'payment_mode': exp.payment_mode if 'payment_mode' in exp._fields else '',
                'log_rows': log_rows,
                'total_hours': total_hours,
                'total_wage': total_wage,
                'expense_total': exp.total_amount or 0.0,
            })
        return {
            'doc_ids': expenses.ids,
            'doc_model': self._name,
            'docs': expenses,
            'rows': rows,
        }
