from odoo import fields, models, api


class FarmProbeCalibration(models.Model):
    _name = 'farm.probe.calibration'
    _description = 'Probe Calibration Record (CL-45, GAP 4.15)'
    _order = 'calibrated_on desc, id'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('probe_name', 'calibrated_on')
    def _compute_display_name(self):
        for rec in self:
            if rec.probe_name and rec.calibrated_on:
                rec.display_name = f"{rec.probe_name} — {rec.calibrated_on}"
            else:
                rec.display_name = 'New Calibration'

    probe_name = fields.Char(
        string='Probe',
        required=True,
        help='Which probe/meter was calibrated, e.g. "EC/pH meter #1"',
    )
    calibrated_on = fields.Date(
        string='Calibrated On',
        required=True,
        default=fields.Date.context_today,
    )
    next_due = fields.Date(
        string='Next Due',
        compute='_compute_next_due',
        store=True,
        readonly=False,
        help='GAP 4.15: precision instruments must be accuracy-checked at least once per year',
    )

    @api.depends('calibrated_on')
    def _compute_next_due(self):
        from datetime import date
        for rec in self:
            if rec.calibrated_on:
                rec.next_due = date(rec.calibrated_on.year + 1,
                                    rec.calibrated_on.month,
                                    rec.calibrated_on.day)
            else:
                rec.next_due = False

    notes = fields.Text(string='Notes')

    def action_overdue_check(self):
        """Cron-free helper: True when any record is past its due date."""
        from datetime import date
        today = fields.Date.context_today(self)
        self.ensure_one()
        return bool(self.next_due and self.next_due < today)