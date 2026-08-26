from odoo import fields, models, api
from odoo.exceptions import UserError


class FarmTemperatureLog(models.Model):
    _name = 'farm.temperature.log'
    _description = 'Temperature Log (CL-37)'
    _order = 'date desc, id'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )
    date = fields.Date(
        string='Reading Date',
        required=True,
        default=fields.Date.context_today,
    )
    min_temp = fields.Float(
        string='Min Temp (°C)',
        required=True,
    )
    max_temp = fields.Float(
        string='Max Temp (°C)',
        required=True,
    )
    range_ok = fields.Boolean(
        string='Within Safe Range',
        compute='_compute_range_ok',
        store=True,
        help='True when min ≥ 10°C and max ≤ 35°C — the safe band for leafy greens',
    )
    notes = fields.Text(string='Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('canceled', 'Canceled'),
    ], string='Status', default='draft', required=True)
    # CL-08: GAP 3.8.1 signature pair
    performed_by = fields.Char(
        string='Performed By',
        help='Worker who took the reading (GAP 3.8.1 signature)',
    )
    confirmed_by = fields.Many2one(
        'res.users',
        string='Confirmed By',
        readonly=True,
        copy=False,
        help='User who confirmed the record (bound at confirm = digital signature)',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    ref = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        help='Auto-generated reference number',
    )

    @api.depends('date')
    def _compute_display_name(self):
        for record in self:
            record.display_name = str(record.date) if record.date else 'New Reading'

    @api.depends('min_temp', 'max_temp')
    def _compute_range_ok(self):
        for record in self:
            record.range_ok = record.min_temp >= 10.0 and record.max_temp <= 35.0

    def write(self, vals):
        """Block editing non-draft records."""
        for record in self:
            if record.state != 'draft':
                other_fields = [k for k in vals if k != 'state']
                if other_fields:
                    raise UserError(f'Cannot edit a {record.state} temperature log. Only draft records can be modified.')
        return super().write(vals)

    def action_confirm(self):
        """Confirm the temperature log (GAP 3.8.1: signed by the worker)."""
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Can only confirm draft logs. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'confirmed', 'confirmed_by': self.env.user.id})
        return True

    def action_cancel(self):
        """Cancel the temperature log."""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(f'Can only cancel confirmed logs. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'canceled'})
        return True

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if not vals.get('ref'):
                vals['ref'] = self.env['ir.sequence'].next_by_code('farm.temperature.log') or '/'
        return super(FarmTemperatureLog, self).create(vals_list)
