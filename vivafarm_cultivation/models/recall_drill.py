from odoo import fields, models, api
from odoo.exceptions import UserError
import time


class FarmRecallDrill(models.Model):
    _name = 'farm.recall.drill'
    _description = 'Recall Drill (CL-33)'
    _rec_name = 'packed_lot_id'

    packed_lot_id = fields.Many2one(
        'stock.lot',
        string='Packed Lot',
        required=True,
        help='The packed lot being traced',
    )
    drill_date = fields.Date(
        string='Drill Date',
        default=fields.Date.context_today,
        required=True,
    )
    order_count = fields.Integer(
        string='Orders Found',
        compute='_compute_drill',
        store=True,
        help='Number of sales orders referencing this lot',
    )
    customer_list = fields.Text(
        string='Customers',
        compute='_compute_drill',
        store=True,
        help='Customers who bought from this lot (one per line)',
    )
    trace_time_seconds = fields.Integer(
        string='Trace Time (s)',
        compute='_compute_drill',
        store=True,
        help='Seconds the drill took — GAP goal is ≤ 15 minutes (900s). Stored at drill time so list and form agree.',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Completed'),
        ('canceled', 'Canceled'),
    ], string='Status', default='draft', required=True)

    @api.depends('packed_lot_id')
    def _compute_drill(self):
        """CL-33: list every customer who bought from the packed lot.

        Uses sale.order.line.packed_lot_id (CL-19) — loose sales stay
        traceable, so the recall covers both packed and loose sales.
        """
        for record in self:
            start = time.time()
            lines = self.env['sale.order.line'].search([
                ('packed_lot_id', '=', record.packed_lot_id.id),
            ])
            orders = lines.mapped('order_id')
            record.order_count = len(orders)
            names = sorted(set(orders.mapped('partner_id.name') or []))
            record.customer_list = '\n'.join(names) if names else 'No sales found for this lot'
            record.trace_time_seconds = int((time.time() - start) * 1000)

    def action_complete(self):
        """Complete the drill (record the exercise)."""
        for record in self:
            if record.state != 'draft':
                raise UserError('Drill already completed.')
        self.write({'state': 'done'})
        return True

    def action_cancel(self):
        """Cancel the drill."""
        for record in self:
            if record.state not in ('draft', 'done'):
                raise UserError(f'Cannot cancel drill in state "{record.state}".')
        self.write({'state': 'canceled'})
        return True
