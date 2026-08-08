from datetime import timedelta

from odoo import api, fields, models
from odoo.tools import format_amount


class GapReportWizard(models.TransientModel):
    """Period picker for GAP farm log reports.

    Standard wizard->report pattern (same as tax.report.wizard): the wizard
    stores the period (+ optional filters), the Print button opens the QWeb
    report bound to this model, and the report data models below compute the
    rows from farm.log records in the selected period.
    """

    _name = 'gap.report.wizard'
    _description = 'GAP Farm Log Report Wizard'

    report_type = fields.Selection([
        ('worker_log', 'Worker Daily Log (บันทึกการทำงาน)'),
    ], string='Report', required=True, default='worker_log')
    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    worker_name = fields.Char(
        string='Worker Name',
        help='Leave empty for all workers')
    bench_id = fields.Many2one(
        'farm.location',
        string='Bench',
        domain="[('location_type', 'in', ('nursery', 'bench'))]",
        help='Leave empty for all locations')

    @api.onchange('date_from', 'date_to')
    def _onchange_dates(self):
        # Keep a sane default when the user clears a field.
        if not self.date_from and self.date_to:
            self.date_from = fields.Date.add(self.date_to, months=-1, day=1)
        if not self.date_to and self.date_from:
            self.date_to = fields.Date.add(self.date_from, months=1, day=1) - timedelta(days=1)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        res['date_to'] = today.replace(day=1) - timedelta(days=1)
        res['date_from'] = res['date_to'].replace(day=1)
        return res

    def action_report_gap(self):
        """Print the selected GAP report for the chosen period."""
        self.ensure_one()
        report_name = 'vivafarm_gap_reports.report_worker_log'
        return self.env['ir.actions.report']._get_report_from_name(
            report_name
        ).report_action(self)


class ReportWorkerLog(models.AbstractModel):
    """Data model for the Worker Daily Log QWeb report.

    Odoo 19 renders QWeb PDFs by looking up a model named
    ``report.<module>.<template>`` and calling its ``_get_report_values``.
    Without this model the renderer falls back to a plain ``docs`` browse
    and the log rows/totals are never injected.
    """

    _name = 'report.vivafarm_gap_reports.report_worker_log'
    _description = 'Worker Daily Log Report Data'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['gap.report.wizard'].browse(docids)
        domain = [
            ('state', '=', 'confirmed'),
            ('date', '>=', wizard.date_from),
            ('date', '<=', wizard.date_to),
        ]
        if wizard.worker_name:
            domain.append(('worker_name', 'ilike', wizard.worker_name))
        logs = self.env['farm.worker.log'].search(domain, order='date, worker_name, id')
        currency = self.env.company.currency_id
        rows = []
        for log in logs:
            rows.append({
                'date': log.date,
                'worker': log.worker_name,
                'id_number': log.worker_id_number or '',
                'task': log.task_description or '',
                'hours': log.working_hours,
                'wage': format_amount(self.env, log.wage_amount, currency),
                'safety': 'Yes' if log.safety_briefing else 'No',
                'lots': ', '.join(log.lot_ids.mapped('name')) or '',
            })
        totals = {
            'wage': format_amount(self.env, sum(log.wage_amount for log in logs), currency),
            'hours': sum(log.working_hours for log in logs),
        }
        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'rows': rows,
            'totals': totals,
            'date_from': wizard.date_from,
            'date_to': wizard.date_to,
            'report_type': wizard.report_type,
        }
