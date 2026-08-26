from odoo import fields, models, api
from odoo.exceptions import UserError


class FarmNutrientMix(models.Model):
    _name = 'farm.nutrient.mix'
    _description = 'Nutrient Mixing Record (F-03)'
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
    tank_name = fields.Char(
        string='Tank',
        required=True,
        help='Tank identifier (e.g. Tank A)',
    )
    recipe_id = fields.Many2one(
        'vivafarm.recipe',
        string='Recipe',
        help='Crop recipe the mix is for',
    )
    concentrate_a_ml = fields.Float(
        string='Concentrate A (ml)',
        help='Nutrient A concentrate volume',
    )
    concentrate_b_ml = fields.Float(
        string='Concentrate B (ml)',
        help='Nutrient B concentrate volume',
    )
    water_liters = fields.Float(
        string='Water (L)',
        help='Raw water volume',
    )
    target_ec = fields.Float(
        string='Target EC',
        digits=(4, 2),
        help='Target EC after mixing',
    )
    target_ph = fields.Float(
        string='Target pH',
        digits=(3, 1),
        help='Target pH after mixing',
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
        help='Worker who mixed the nutrients (GAP 3.8.1 signature)',
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

    @api.depends('date', 'tank_name')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.date:
                parts.append(str(record.date))
            if record.tank_name:
                parts.append(record.tank_name)
            record.display_name = ' / '.join(parts) if parts else 'New Mix'

    def write(self, vals):
        """Block editing non-draft records."""
        for record in self:
            if record.state != 'draft':
                other_fields = [k for k in vals if k != 'state']
                if other_fields:
                    raise UserError(f'Cannot edit a {record.state} mix record. Only draft records can be modified.')
        return super().write(vals)

    def action_confirm(self):
        """Confirm the mix record (GAP 3.8.1: signed by the worker)."""
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Can only confirm draft mix records. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'confirmed', 'confirmed_by': self.env.user.id})
        return True

    def action_cancel(self):
        """Cancel the mix record."""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(f'Can only cancel confirmed mix records. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'canceled'})
        return True

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if not vals.get('ref'):
                vals['ref'] = self.env['ir.sequence'].next_by_code('farm.nutrient.mix') or '/'
        return super(FarmNutrientMix, self).create(vals_list)
