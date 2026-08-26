from odoo import fields, models, api
from odoo.exceptions import UserError


class FarmPhysicalCount(models.Model):
    _name = 'farm.physical.count'
    _description = 'Physical Inventory Count (CL-30)'
    _order = 'date desc, id'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )
    date = fields.Date(
        string='Count Date',
        required=True,
        default=fields.Date.context_today,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        help='Product counted (packed goods, raw materials, consumables)',
    )
    counted_qty = fields.Float(
        string='Counted Qty',
        help='Quantity physically counted',
    )
    system_qty = fields.Float(
        string='System Qty',
        compute='_compute_system_qty',
        help='Quantity per the system (stock on hand) at count time',
    )
    variance = fields.Float(
        string='Variance',
        compute='_compute_variance',
        help='Counted minus system quantity — negative = shortage, positive = surplus',
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
        help='Worker who performed the count (GAP 3.8.1 signature)',
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

    @api.depends('date', 'product_id')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.date:
                parts.append(str(record.date))
            if record.product_id:
                parts.append(record.product_id.name)
            record.display_name = ' / '.join(parts) if parts else 'New Count'

    @api.depends('product_id')
    def _compute_system_qty(self):
        """CL-30: system quantity = free quantity on hand (from quant)."""
        for record in self:
            if not record.product_id:
                record.system_qty = 0.0
                continue
            qty = 0.0
            quants = self.env['stock.quant'].search([
                ('product_id', '=', record.product_id.id),
                ('location_id.usage', '=', 'internal'),
            ])
            qty = sum(q.quantity for q in quants)
            record.system_qty = qty

    @api.depends('counted_qty', 'system_qty')
    def _compute_variance(self):
        for record in self:
            record.variance = record.counted_qty - record.system_qty

    def write(self, vals):
        """Block editing non-draft records."""
        for record in self:
            if record.state != 'draft':
                other_fields = [k for k in vals if k != 'state']
                if other_fields:
                    raise UserError(f'Cannot edit a {record.state} count. Only draft records can be modified.')
        return super().write(vals)

    def action_confirm(self):
        """Confirm the count (GAP 3.8.1: signed by the worker)."""
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Can only confirm draft counts. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'confirmed', 'confirmed_by': self.env.user.id})
        return True

    def action_cancel(self):
        """Cancel the count."""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(f'Can only cancel confirmed counts. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'canceled'})
        return True

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if not vals.get('ref'):
                vals['ref'] = self.env['ir.sequence'].next_by_code('farm.physical.count') or '/'
        return super(FarmPhysicalCount, self).create(vals_list)
