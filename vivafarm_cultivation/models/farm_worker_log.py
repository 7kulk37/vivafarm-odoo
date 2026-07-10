from odoo import api, fields, models
from odoo.exceptions import UserError


class FarmWorkerLog(models.Model):
    _name = 'farm.worker.log'
    _description = 'Farm Worker Log - Daily Worker Activity'
    _order = 'date desc, id'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    worker_name = fields.Char(
        string='Worker Name',
        required=True,
        help="Worker's full name as shown on ID card",
    )
    worker_id_number = fields.Char(
        string='ID Number',
        help='National ID number (for GAP worker registration)',
    )
    task_description = fields.Text(
        string='Task Description',
        required=True,
        help='What work was done (e.g. "Harvest C1+C2, pack 10kg")',
    )
    safety_briefing = fields.Boolean(
        string='Safety Briefing Given',
        default=True,
        help='GAP hygiene and safety briefing confirmed',
    )
    wage_amount = fields.Float(
        string='Wage (THB)',
        digits=(8, 0),
        default=350.0,
        help='Daily wage in Thai Baht',
    )
    working_hours = fields.Float(
        string='Working Hours',
        digits=(4, 1),
        default=8.0,
        help='Hours worked (default 8)',
    )
    lot_ids = fields.Many2many(
        'stock.lot',
        string='Batches Worked',
        help='Which farm batches were worked on today',
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('canceled', 'Canceled'),
        ],
        string='Status',
        default='draft',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    @api.depends('date', 'worker_name')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.date:
                parts.append(str(record.date))
            if record.worker_name:
                parts.append(record.worker_name)
            record.display_name = ' / '.join(parts) if parts else 'New Worker Log'

    def write(self, vals):
        """Block editing non-draft records."""
        for record in self:
            if record.state != 'draft':
                other_fields = [k for k in vals if k != 'state']
                if other_fields:
                    raise UserError(f'Cannot edit a {record.state} worker log. Only draft logs can be modified.')
        return super().write(vals)

    def action_confirm(self):
        """Confirm the worker log. Only works from draft state."""
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Can only confirm draft worker logs. Log {record.display_name} is in state "{record.state}".')
        self.write({'state': 'confirmed'})
        return True

    def action_cancel(self):
        """Cancel the worker log. Only works from confirmed state."""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(f'Can only cancel confirmed worker logs. Log {record.display_name} is in state "{record.state}".')
        self.write({'state': 'canceled'})
        return True