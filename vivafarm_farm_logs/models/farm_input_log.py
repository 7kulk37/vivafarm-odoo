from odoo import fields, models, api


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
        'stock.location',
        string='Bench',
        required=True,
        domain="[('usage', '=', 'internal')]",
        help='NFT bench location (C1-F6)',
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
    adjustment_type = fields.Selection(
        [
            ('none', 'No adjustment'),
            ('nutrient', 'Nutrient added'),
            ('acid', 'Acid added'),
        ],
        string='Adjustment',
        default='none',
        required=True,
    )
    adjustment_amount = fields.Float(
        string='Adjustment Amount',
        digits=(6, 1),
        help='Amount in grams (nutrient) or ml (acid)',
    )
    notes = fields.Text(string='Notes')
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
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

    @api.depends('date', 'bench_id')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.date:
                parts.append(str(record.date))
            if record.bench_id:
                parts.append(record.bench_id.name)
            record.display_name = ' / '.join(parts) if parts else 'New Input Log'

    def action_confirm(self):
        """Confirm the input log. Works from both list and form views."""
        self.write({'state': 'confirmed'})
        return True

    def action_draft(self):
        """Reset to draft."""
        self.write({'state': 'draft'})
        return True