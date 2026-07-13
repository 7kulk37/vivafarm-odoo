from odoo import fields, models, api
from odoo.exceptions import UserError


class FarmInputLog(models.Model):
    _name = 'farm.input.log'
    _description = 'Farm Input Log - Daily EC/pH Readings'
    _order = 'date desc, bench_id'
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
    bench_id = fields.Many2one(
        'farm.location',
        string='Location',
        required=True,
        domain="[('location_type', 'in', ('nursery', 'bench'))]",
        help='Nursery or NFT bench location',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Batch (Lot)',
        required=True,
        help='Farm batch on this bench (YYWW-BENCH)',
    )
    crop_id = fields.Many2one(
        'product.product',
        string='Crop',
        related='lot_id.product_id',
        readonly=True,
        store=False,
    )
    ec_value = fields.Float(
        string='EC (mS/cm)',
        digits=(4, 2),
        help='Electrical conductivity reading',
    )
    ph_value = fields.Float(
        string='pH',
        digits=(3, 1),
        help='pH reading',
    )
    nutrient_adjustment = fields.Float(
        string='Nutrient (ml)',
        digits=(6, 1),
        default=0.0,
        help='Nutrient concentrate added in ml',
    )
    acid_adjustment = fields.Float(
        string='Acid (ml)',
        digits=(6, 1),
        default=0.0,
        help='Nitric acid added in ml',
    )
    raw_water_liters = fields.Float(
        string='Raw Water (L)',
        digits=(6, 1),
        default=0.0,
        help='Raw water added in liters',
    )
    mixing_liters = fields.Float(
        string='Mixing (L)',
        digits=(6, 1),
        default=0.0,
        help='Total mixing volume in liters (for special cases like dumping contaminated reservoir)',
    )
    notes = fields.Text(string='Notes')
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
            record.display_name = ' / '.join(parts) if parts else 'New Input Log'

    def write(self, vals):
        """Block editing non-draft records."""
        for record in self:
            if record.state != 'draft':
                # Allow only state changes (confirm/cancel)
                other_fields = [k for k in vals if k != 'state']
                if other_fields:
                    raise UserError(f'Cannot edit a {record.state} input log. Only draft logs can be modified.')
        return super().write(vals)

    def action_confirm(self):
        """Confirm the input log. Only works from draft state."""
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Can only confirm draft input logs. Log {record.display_name} is in state "{record.state}".')
        self.write({'state': 'confirmed'})
        return True

    def action_cancel(self):
        """Cancel the input log. Only works from confirmed state."""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(f'Can only cancel confirmed input logs. Log {record.display_name} is in state "{record.state}".')
        self.write({'state': 'canceled'})
        return True

    def unlink(self):
        """Block deletion of non-draft input logs."""
        for record in self:
            if record.state != 'draft':
                raise UserError(
                    f'Cannot delete input log {record.display_name} '
                    f'in state "{record.state}". Cancel it first.')
        return super(FarmInputLog, self).unlink()

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if not vals.get('ref'):
                vals['ref'] = self.env['ir.sequence'].next_by_code('farm.input.log') or '/'
        return super(FarmInputLog, self).create(vals_list)