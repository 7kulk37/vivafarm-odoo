from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # CL-19: loose (unpacked) sales trace to a packed lot (GAP 3.8.3)
    packed_lot_id = fields.Many2one(
        'stock.lot',
        string='Packed Lot',
        help='The packed lot this sale line draws from — loose sales stay traceable',
    )
