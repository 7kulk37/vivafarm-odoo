# Over-receive guard: incoming moves (purchase receipts) may not receive
# more than the ordered quantity. Odoo allows over-receiving by default;
# VivaFarm policy is to pay for exactly what was ordered.
#
# Over-delivery guard: outgoing moves (customer deliveries) may not deliver
# more than the ordered quantity. Odoo allows over-delivery by default;
# VivaFarm policy is to ship exactly what was ordered.
#
# Negative-stock guard: consumption moves may not consume more than the
# on-hand quantity at the source location. Odoo allows negative stock by
# default; VivaFarm policy is that stock never goes negative (you cannot
# consume what you do not have).
#
# The guard checks MOVE LINES, not moves: a delivery move's location_id is
# the product's default source (e.g. WH/Stock) while the actual goods are
# picked from a different internal location (e.g. Packed Goods) via the move
# lines. Checking the move's location would false-positive on deliveries.
from collections import defaultdict

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

        # Over-delivery guard: outgoing moves (customer deliveries) may not
        # deliver more than the ordered quantity.
        for move in self:
            if (move.picking_id.picking_type_id.code == 'outgoing'
                    and move.product_uom.compare(move.quantity, move.product_uom_qty) > 0):
                raise UserError(_(
                    "Cannot deliver %s %s of %s: ordered quantity is %s %s. "
                    "Over-delivery is not allowed.",
                    move.quantity, move.product_uom.name,
                    move.product_id.display_name,
                    move.product_uom_qty, move.product_uom.name,
                ))

        # Negative-stock guard: aggregate consumption per (product, source)
        # across all move lines being done, so two lines of the same product
        # from the same location cannot jointly exceed on-hand.
        consumption = defaultdict(float)
        for move in self:
            for ml in move.move_line_ids:
                src = ml.location_id
                dst = ml.location_dest_id
                if (src.usage == 'internal' and src != dst
                        and ml.product_id.is_storable
                        and ml.quantity > 0):
                    consumption[(ml.product_id.id, src.id)] += ml.quantity

        for (product_id, src_id), qty in consumption.items():
            product = self.env['product.product'].browse(product_id)
            src = self.env['stock.location'].browse(src_id)
            on_hand = sum(self.env['stock.quant'].search([
                ('product_id', '=', product_id),
                ('location_id', '=', src_id),
            ]).mapped('quantity'))
            if on_hand + 1e-9 < qty:
                raise UserError(_(
                    "Cannot consume %s %s of %s: only %s %s on hand at %s. "
                    "Negative stock is not allowed.",
                    qty, product.uom_id.name,
                    product.display_name,
                    on_hand, product.uom_id.name, src.name,
                ))

        return super()._action_done(cancel_backorder=cancel_backorder)
