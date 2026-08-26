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
    # CL-27: F-04 reading time (GAP 3.5.1 — when the reading was taken)
    reading_time = fields.Datetime(
        string='Reading Time',
        help='When the EC/pH reading was taken (GAP 3.5.1)',
    )
    # CL-27: EC/pH probe calibration trail (GAP 3.5.2)
    probe_last_calibrated = fields.Date(
        string='Probe Last Calibrated',
        help='Date the EC/pH probe was last calibrated',
    )
    probe_calibration_due = fields.Date(
        string='Probe Calibration Due',
        help='Date the probe calibration expires (typically +30 days)',
    )
    # CL-28: out-of-band detection + correction trio (GAP 3.5.1)
    is_out_of_band = fields.Boolean(
        string='Out of Band', compute='_compute_out_of_band', store=True,
        help='True when EC or pH is outside the recipe target band',
    )
    recheck_ec_value = fields.Float(
        string='Re-check EC', digits=(4, 2),
        help='EC after correction (re-check reading)',
    )
    recheck_ph_value = fields.Float(
        string='Re-check pH', digits=(3, 1),
        help='pH after correction (re-check reading)',
    )
    recheck_time = fields.Datetime(
        string='Re-check Time',
        help='When the re-check reading was taken',
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
    # CL-08: GAP 3.8.1 signature pair — who did the work + who confirmed
    performed_by = fields.Char(
        string='Performed By',
        help='Worker who performed the task (GAP 3.8.1 signature)',
    )
    confirmed_by = fields.Many2one(
        'res.users',
        string='Confirmed By',
        readonly=True,
        copy=False,
        help='User who confirmed the record (bound at confirm = digital signature)',
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

    @api.depends('ec_value', 'ph_value', 'lot_id')
    def _compute_out_of_band(self):
        """CL-28: flag when EC or pH is outside the recipe target band."""
        for record in self:
            recipe = record.lot_id.cultivation_recipe_id if hasattr(record.lot_id, 'cultivation_recipe_id') else False
            if not recipe:
                recipe = self.env['vivafarm.recipe'].search([
                    ('crop_id', '=', record.lot_id.product_id.id),
                ], limit=1)
            if not recipe:
                record.is_out_of_band = False
                continue
            ec_ok = (not recipe.target_ec_min or record.ec_value >= recipe.target_ec_min) and \
                    (not recipe.target_ec_max or record.ec_value <= recipe.target_ec_max)
            ph_ok = (not recipe.target_ph_min or record.ph_value >= recipe.target_ph_min) and \
                    (not recipe.target_ph_max or record.ph_value <= recipe.target_ph_max)
            record.is_out_of_band = not (ec_ok and ph_ok)

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
        """Confirm the input log. Only works from draft state.

        CL-08: confirm binds the confirming user as the digital signature
        (GAP 3.8.1) — the record becomes immutable.
        """
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Can only confirm draft input logs. Log {record.display_name} is in state "{record.state}".')
        self.write({'state': 'confirmed', 'confirmed_by': self.env.user.id})
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