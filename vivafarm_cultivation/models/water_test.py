from odoo import fields, models, api
from odoo.exceptions import UserError


class FarmWaterTest(models.Model):
    _name = 'farm.water.test'
    _description = 'Water Test Record (F-02)'
    _order = 'date desc, id'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )
    date = fields.Date(
        string='Test Date',
        required=True,
        default=fields.Date.context_today,
    )
    source = fields.Char(
        string='Water Source',
        required=True,
        help='Source tested (rain tank, tap, well) — a source change forces a NEW test',
    )
    result = fields.Selection([
        ('pass', 'Pass'),
        ('fail', 'Fail'),
    ], string='Result', required=True)
    lab_name = fields.Char(
        string='Lab',
        help='Accredited lab that ran the test',
    )
    report_ref = fields.Char(
        string='Report Ref',
        help='Lab report reference number',
    )
    corrective_action = fields.Text(
        string='Corrective Action',
        help='What was done after a fail (flush, UV, source change)',
    )
    retest_of_id = fields.Many2one(
        'farm.water.test',
        string='Retest Of',
        help='The failed test this is a retest of',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('canceled', 'Canceled'),
    ], string='Status', default='draft', required=True)
    # CL-08: GAP 3.8.1 signature pair
    performed_by = fields.Char(
        string='Performed By',
        help='Worker who took the sample (GAP 3.8.1 signature)',
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

    @api.depends('date', 'source')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.date:
                parts.append(str(record.date))
            if record.source:
                parts.append(record.source)
            record.display_name = ' / '.join(parts) if parts else 'New Water Test'

    def write(self, vals):
        """Block editing non-draft records."""
        for record in self:
            if record.state != 'draft':
                other_fields = [k for k in vals if k != 'state']
                if other_fields:
                    raise UserError(f'Cannot edit a {record.state} water test. Only draft records can be modified.')
        return super().write(vals)

    def action_confirm(self):
        """Confirm the water test (GAP 3.8.1: signed by the worker)."""
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Can only confirm draft water tests. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'confirmed', 'confirmed_by': self.env.user.id})
        return True

    def action_cancel(self):
        """Cancel the water test."""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(f'Can only cancel confirmed water tests. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'canceled'})
        return True

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if not vals.get('ref'):
                vals['ref'] = self.env['ir.sequence'].next_by_code('farm.water.test') or '/'
        return super(FarmWaterTest, self).create(vals_list)
