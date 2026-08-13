# Over-receive guard: incoming moves (purchase receipts) may not receive
# more than the ordered quantity. Odoo allows over-receiving by default;
# VivaFarm policy is to pay for exactly what was ordered.
from odoo import _, models
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        for move in self:
            if (move.picking_id.picking_type_id.code == 'incoming'
                    and move.product_uom.compare(move.quantity, move.product_uom_qty) > 0):
                raise UserError(_(
                    "Cannot receive %s %s of %s: ordered quantity is %s %s. "
                    "Over-receiving is not allowed.",
                    move.quantity, move.product_uom.name,
                    move.product_id.display_name,
                    move.product_uom_qty, move.product_uom.name,
                ))
        return super()._action_done(cancel_backorder=cancel_backorder)
