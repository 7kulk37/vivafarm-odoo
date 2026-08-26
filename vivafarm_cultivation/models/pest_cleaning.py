from odoo import fields, models, api
from odoo.exceptions import UserError


class FarmPestMonitor(models.Model):
    _name = 'farm.pest.monitor'
    _description = 'Pest Monitoring Log (F-05)'
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
    )
    bench_id = fields.Many2one(
        'farm.location',
        string='Location',
        domain="[('location_type', 'in', ('nursery', 'bench'))]",
        help='Nursery or bench monitored',
    )
    pest_found = fields.Char(
        string='Pest Found',
        help='Pest/disease observed, or "None"',
    )
    action_taken = fields.Text(
        string='Action Taken',
        help='What was done (removal, treatment, monitoring)',
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
        help='Worker who performed the monitoring (GAP 3.8.1 signature)',
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

    @api.depends('date', 'bench_id')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.date:
                parts.append(str(record.date))
            if record.bench_id:
                parts.append(record.bench_id.name)
            record.display_name = ' / '.join(parts) if parts else 'New Pest Log'

    def write(self, vals):
        """Block editing non-draft records."""
        for record in self:
            if record.state != 'draft':
                other_fields = [k for k in vals if k != 'state']
                if other_fields:
                    raise UserError(f'Cannot edit a {record.state} pest log. Only draft records can be modified.')
        return super().write(vals)

    def action_confirm(self):
        """Confirm the pest log (GAP 3.8.1: signed by the worker)."""
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Can only confirm draft pest logs. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'confirmed', 'confirmed_by': self.env.user.id})
        return True

    def action_cancel(self):
        """Cancel the pest log."""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(f'Can only cancel confirmed pest logs. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'canceled'})
        return True

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if not vals.get('ref'):
                vals['ref'] = self.env['ir.sequence'].next_by_code('farm.pest.monitor') or '/'
        return super(FarmPestMonitor, self).create(vals_list)


class FarmCleaningLog(models.Model):
    _name = 'farm.cleaning.log'
    _description = 'Cleaning Log (F-09)'
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
    )
    area = fields.Char(
        string='Area',
        required=True,
        help='Area cleaned (packing area, nursery, benches, tools)',
    )
    method = fields.Char(
        string='Method',
        help='Cleaning method (sanitizer wipe, rinse, etc.)',
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
        help='Worker who performed the cleaning (GAP 3.8.1 signature)',
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

    @api.depends('date', 'area')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.date:
                parts.append(str(record.date))
            if record.area:
                parts.append(record.area)
            record.display_name = ' / '.join(parts) if parts else 'New Cleaning Log'

    def write(self, vals):
        """Block editing non-draft records."""
        for record in self:
            if record.state != 'draft':
                other_fields = [k for k in vals if k != 'state']
                if other_fields:
                    raise UserError(f'Cannot edit a {record.state} cleaning log. Only draft records can be modified.')
        return super().write(vals)

    def action_confirm(self):
        """Confirm the cleaning log (GAP 3.8.1: signed by the worker)."""
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Can only confirm draft cleaning logs. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'confirmed', 'confirmed_by': self.env.user.id})
        return True

    def action_cancel(self):
        """Cancel the cleaning log."""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(f'Can only cancel confirmed cleaning logs. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'canceled'})
        return True

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if not vals.get('ref'):
                vals['ref'] = self.env['ir.sequence'].next_by_code('farm.cleaning.log') or '/'
        return super(FarmCleaningLog, self).create(vals_list)
