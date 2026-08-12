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
        ('input_log', 'Daily Input Log EC/pH (บันทึกค่า EC/pH)'),
        ('wage_sheet', 'Daily Wage Sheet (บัญชีจ่ายค่าจ้างรายวัน)'),
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
        report_name = {
            'input_log': 'vivafarm_gap_reports.report_input_log',
            'wage_sheet': 'vivafarm_gap_reports.report_wage_sheet',
        }.get(self.report_type, 'vivafarm_gap_reports.report_worker_log')
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


class ReportInputLog(models.AbstractModel):
    """Data model for the Daily Input Log (EC/pH) QWeb report.

    Period report over farm.input.log records, optionally filtered by
    bench/location. 1350+ records exist in the demo year, so the wizard
    defaults to a single month — wide periods render multi-page but stay
    within wkhtmltopdf limits.
    """

    _name = 'report.vivafarm_gap_reports.report_input_log'
    _description = 'Daily Input Log EC/pH Report Data'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['gap.report.wizard'].browse(docids)
        domain = [
            ('state', '=', 'confirmed'),
            ('date', '>=', wizard.date_from),
            ('date', '<=', wizard.date_to),
        ]
        if wizard.bench_id:
            domain.append(('bench_id', '=', wizard.bench_id.id))
        logs = self.env['farm.input.log'].search(domain, order='date, bench_id, id')
        rows = []
        for log in logs:
            rows.append({
                'date': log.date,
                'bench': log.bench_id.name or '',
                'lot': log.lot_id.name or '',
                'crop': log.crop_id.name or '',
                'ec': log.ec_value,
                'ph': log.ph_value,
                'nutrient': log.nutrient_adjustment,
                'acid': log.acid_adjustment,
                'raw_water': log.raw_water_liters,
                'mixing': log.mixing_liters,
                'notes': log.notes or '',
            })
        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'rows': rows,
            'date_from': wizard.date_from,
            'date_to': wizard.date_to,
            'report_type': wizard.report_type,
            'bench_filter': wizard.bench_id.name or '',
        }


class ReportWageSheet(models.AbstractModel):
    """Data model for the Daily Wage Sheet (บัญชีจ่ายค่าจ้างรายวัน).

    Labor Protection Act มาตรา 76 (wage payment records) + มาตรา 114
    (employee register) — the supporting evidence behind PND1. NOT a GAP
    form (มกษ. 9001-2564 has no wage clause).

    Aggregates confirmed ``farm.worker.log`` rows in the selected period,
    grouped by worker, one row per day with a signature column (the
    worker signs next to each day's wage — same ลงชื่อ pattern as GAP
    3.8.1). Totals per worker + grand totals.
    """

    _name = 'report.vivafarm_gap_reports.report_wage_sheet'
    _description = 'Daily Wage Sheet Report Data'

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
        logs = self.env['farm.worker.log'].search(
            domain, order='worker_name, date, id')
        currency = self.env.company.currency_id

        # Group by worker, keep insertion order (first seen).
        workers = []
        by_name = {}
        for log in logs:
            name = log.worker_name
            if name not in by_name:
                by_name[name] = {
                    'worker': name,
                    'id_number': log.worker_id_number or '',
                    'rows': [],
                    'total_hours': 0.0,
                    'total_wage': 0.0,
                }
                workers.append(by_name[name])
            g = by_name[name]
            g['rows'].append({
                'date': log.date,
                'task': log.task_description or '',
                'hours': log.working_hours,
                'wage': log.wage_amount,
            })
            g['total_hours'] += log.working_hours
            g['total_wage'] += log.wage_amount

        grand_hours = sum(g['total_hours'] for g in workers)
        grand_wage = sum(g['total_wage'] for g in workers)
        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'workers': workers,
            'grand_hours': grand_hours,
            'grand_wage': format_amount(self.env, grand_wage, currency),
            'date_from': wizard.date_from,
            'date_to': wizard.date_to,
            'report_type': wizard.report_type,
            'worker_filter': wizard.worker_name or '',
        }
