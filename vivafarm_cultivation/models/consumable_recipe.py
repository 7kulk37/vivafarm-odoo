from odoo import fields, models, api


class ConsumableRecipe(models.Model):
    _name = 'consumable.recipe'
    _description = 'Consumable Recipe - defines a material transformation step'
    _order = 'name asc'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(string='Active', default=True)

    # Input products (from WH/Stock or Buffer)
    input_product_a_id = fields.Many2one(
        'product.product', string='Input Product A', required=True,
        domain="[('type', '=', 'consu')]",
        help='Primary input product consumed from WH/Stock')
    input_qty_a = fields.Float(
        string='Input Qty A', required=True, default=1.0,
        help='Base quantity of Input A consumed per batch')
    input_product_b_id = fields.Many2one(
        'product.product', string='Input Product B (optional)',
        domain="[('type', '=', 'consu')]",
        help='Secondary input product (e.g. Raw Water for dilution)')
    input_qty_b = fields.Float(
        string='Input Qty B', default=0.0,
        help='Base quantity of Input B consumed per batch')

    # Output products (to Buffer or Stock)
    output_product_c_id = fields.Many2one(
        'product.product', string='Output Product C', required=True,
        domain="[('type', '=', 'consu')]",
        help='Primary output product created in Buffer')
    output_qty_c = fields.Float(
        string='Output Qty C', required=True, default=1.0,
        help='Base quantity of Output C produced per batch')
    output_product_d_id = fields.Many2one(
        'product.product', string='Output Product D (optional)',
        domain="[('type', '=', 'consu')]",
        help='Secondary output product (e.g. splitting a pack into A and B)')
    output_qty_d = fields.Float(
        string='Output Qty D', default=0.0,
        help='Base quantity of Output D produced per batch')

    # Source/destination flags
    source_is_buffer = fields.Boolean(
        string='Source from Buffer', default=False,
        help='If True, input products are consumed from Cultivation Buffer instead of Stock')
    destination_is_stock = fields.Boolean(
        string='Send to Stock', default=False,
        help='If True, output products go to Stock instead of Cultivation Buffer')

    notes = fields.Text(string='Notes')
