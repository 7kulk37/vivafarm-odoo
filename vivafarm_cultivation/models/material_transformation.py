from odoo import fields, models, api
from odoo.exceptions import UserError


class MaterialTransformation(models.Model):
    _name = 'material.transformation'
    _description = 'Material Transformation - Convert raw materials to intermediate products in Cultivation Buffer'
    _order = 'date desc, id desc'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )
    product_id = fields.Many2one(
        'product.product', string='Raw Material',
        domain="[('type', '=', 'consu')]",
        required=True,
        help='Raw material to convert (e.g. Nutrient A Powder)')
    intermediate_product_id = fields.Many2one(
        'product.product', string='Intermediate Product',
        domain="[('type', '=', 'consu')]",
        required=True,
        help='Resulting intermediate product (e.g. Nutrient A Concentrate)')
    secondary_intermediate_product_id = fields.Many2one(
        'product.product', string='Secondary Intermediate',
        domain="[('type', '=', 'consu')]",
        help='Second intermediate product (e.g. for splitting a pack into A and B powder)')
    secondary_conversion_factor = fields.Float(
        string='Secondary Factor',
        default=0.0,
        help='How many units of secondary intermediate per unit of raw material. '
             'e.g. 1 pack = 1 kg A + 1 kg B (factor=1.0 for both)')
    destination_is_stock = fields.Boolean(
        string='Send to Stock',
        default=False,
        help='If True, intermediate products go to Stock instead of Cultivation Buffer. '
             'Use for split operations where the output is still a raw material for the next step.')
    source_is_buffer = fields.Boolean(
        string='Source from Buffer',
        default=False,
        help='If True, raw material is consumed from Cultivation Buffer instead of Stock. '
             'Use when the raw material was produced by a previous split/transformation.')
    quantity = fields.Float(
        string='Raw Qty',
        required=True,
        default=1.0,
        help='Quantity of raw material to convert')
    intermediate_qty = fields.Float(
        string='Intermediate Qty',
        compute='_compute_intermediate_qty',
        store=True,
        readonly=True,
        help='Quantity of intermediate product produced')
    conversion_factor = fields.Float(
        string='Conversion Factor',
        default=1.0,
        help='How many units of intermediate per unit of raw material. '
             'e.g. 1 kg Nutrient A Powder + 1 L water = 1 L concentrate (factor=1.0). '
             '1 L 68% acid + 9 L water = 10 L diluted (factor=10.0). '
             '1 pack bags = 25 opened bags (factor=25.0).')
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today)
    picking_id = fields.Many2one(
        'stock.picking', string='Stock Move', readonly=True,
        help='The stock transfer created by this transformation')
    return_picking_id = fields.Many2one(
        'stock.picking', string='Stock Return', readonly=True,
        help='The stock transfer created when canceling this transformation')
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    consumable_recipe_id = fields.Many2one(
        'consumable.recipe', string='Consumable Recipe',
        help='Select a consumable recipe to auto-fill products and ratios.',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('canceled', 'Canceled'),
    ], string='Status', default='draft', required=True)

    @api.depends('date', 'product_id')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.date:
                parts.append(str(record.date))
            if record.product_id:
                parts.append(record.product_id.name)
            record.display_name = ' / '.join(parts) if parts else 'New'

    @api.depends('quantity', 'conversion_factor')
    def _compute_intermediate_qty(self):
        for record in self:
            record.intermediate_qty = record.quantity * record.conversion_factor

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            self.intermediate_product_id = False
            self.conversion_factor = 1.0
            return
        name = self.product_id.name
        if 'Nutrient A+B Powder packed' in name:
            inter_a = self.env['product.product'].search([('name', '=', 'Nutrient A Powder')], limit=1)
            inter_b = self.env['product.product'].search([('name', '=', 'Nutrient B Powder')], limit=1)
            if inter_a:
                self.intermediate_product_id = inter_a
                self.conversion_factor = 1.0
            if inter_b:
                self.secondary_intermediate_product_id = inter_b
                self.secondary_conversion_factor = 1.0
            self.destination_is_stock = True
        elif 'Nutrient A Powder' in name:
            inter = self.env['product.product'].search([('name', '=', 'Nutrient A Concentrate')], limit=1)
            if inter:
                self.intermediate_product_id = inter
                self.conversion_factor = 1.0
                self.source_is_buffer = True
        elif 'Nutrient B Powder' in name:
            inter = self.env['product.product'].search([('name', '=', 'Nutrient B Concentrate')], limit=1)
            if inter:
                self.intermediate_product_id = inter
                self.conversion_factor = 1.0
                self.source_is_buffer = True
        elif 'Nitric Acid 68%' in name:
            inter = self.env['product.product'].search([('name', '=', 'Diluted Acid 6.8%')], limit=1)
            if inter:
                self.intermediate_product_id = inter
                self.conversion_factor = 10.0
        elif 'Plastic Bags' in name:
            inter = self.env['product.product'].search([('name', '=', 'Opened Bags')], limit=1)
            if inter:
                self.intermediate_product_id = inter
                self.conversion_factor = 25.0
        elif 'Grow Sponge' in name:
            inter = self.env['product.product'].search([('name', '=', 'Growing Media')], limit=1)
            if inter:
                self.intermediate_product_id = inter
                self.conversion_factor = 96.0
        elif 'Rain Water' in name:
            inter = self.env['product.product'].search([('name', '=', 'Raw Water')], limit=1)
            if inter:
                self.intermediate_product_id = inter
                self.conversion_factor = 1.0

    @api.onchange('consumable_recipe_id')
    def _onchange_consumable_recipe_id(self):
        if not self.consumable_recipe_id:
            return
        recipe = self.consumable_recipe_id
        self.product_id = recipe.input_product_a_id
        self.quantity = recipe.input_qty_a
        self.intermediate_product_id = recipe.output_product_c_id
        self.conversion_factor = recipe.output_qty_c / recipe.input_qty_a if recipe.input_qty_a else 1.0
        self.secondary_intermediate_product_id = recipe.output_product_d_id or False
        self.secondary_conversion_factor = recipe.output_qty_d / recipe.input_qty_a if recipe.input_qty_a and recipe.output_qty_d else 0.0
        self.source_is_buffer = recipe.source_is_buffer
        self.destination_is_stock = recipe.destination_is_stock

    def _get_water_qty(self):
        """Calculate water quantity needed for this transformation based on product name."""
        water_product = self.env['product.product'].search([('name', '=', 'Raw Water')], limit=1)
        if not water_product:
            return 0.0
        name = self.product_id.name or ''
        if 'Nutrient A Powder' in name or 'Nutrient B Powder' in name:
            return self.intermediate_qty
        elif 'Nitric Acid 68%' in name:
            return self.intermediate_qty - self.quantity
        return 0.0

    def action_confirm(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(f'Cannot confirm a transformation in state "{self.state}". Only draft records can be confirmed.')
        if self.quantity <= 0:
            raise UserError('Quantity must be greater than 0.')
        if not self.intermediate_product_id:
            raise UserError('Select an intermediate product.')

        stock_loc = self.env['stock.location'].search([
            ('name', '=', 'Stock'),
        ], limit=1)
        buffer_loc = self.env['stock.location'].search([
            ('name', '=', 'Cultivation Buffer'),
        ], limit=1)
        prod_loc = self.env['stock.location'].search([
            ('usage', '=', 'production'),
        ], limit=1)

        if not stock_loc:
            raise UserError('Stock location not found.')
        if not buffer_loc:
            raise UserError('Cultivation Buffer location not found. Create it first.')
        if not prod_loc:
            raise UserError('Production location not found.')

        int_type = self.env.ref('stock.picking_type_internal', raise_if_not_found=False)
        if not int_type:
            int_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1)

        # Determine water needed for this transformation
        water_product = self.env['product.product'].search([('name', '=', 'Raw Water')], limit=1)
        water_qty = self._get_water_qty()

        secondary_qty = 0.0
        if self.secondary_intermediate_product_id and self.secondary_conversion_factor:
            secondary_qty = self.quantity * self.secondary_conversion_factor

        # Build intermediate moves (Production -> destination)
        inter_moves = [(0, 0, {
            'product_id': self.intermediate_product_id.id,
            'product_uom_qty': self.intermediate_qty,
            'product_uom': self.intermediate_product_id.uom_id.id,
            'location_id': prod_loc.id,
            'location_dest_id': buffer_loc.id,
            'company_id': self.env.company.id,
            'date': self.date or fields.Date.today(),
            'procure_method': 'make_to_stock',
        })]
        if secondary_qty > 0 and self.secondary_intermediate_product_id:
            inter_moves.append((0, 0, {
                'product_id': self.secondary_intermediate_product_id.id,
                'product_uom_qty': secondary_qty,
                'product_uom': self.secondary_intermediate_product_id.uom_id.id,
                'location_id': prod_loc.id,
                'location_dest_id': buffer_loc.id,
                'company_id': self.env.company.id,
                'date': self.date or fields.Date.today(),
                'procure_method': 'make_to_stock',
            }))

        # Determine raw material source location
        raw_source_loc = buffer_loc if self.source_is_buffer else stock_loc

        # Build raw material moves (main product + water if needed)
        raw_moves = [(0, 0, {
            'product_id': self.product_id.id,
            'product_uom_qty': self.quantity,
            'product_uom': self.product_id.uom_id.id,
            'location_id': raw_source_loc.id,
            'location_dest_id': prod_loc.id,
            'company_id': self.env.company.id,
            'date': self.date or fields.Date.today(),
            'procure_method': 'make_to_stock',
        })]
        if water_qty > 0 and water_product:
            raw_moves.append((0, 0, {
                'product_id': water_product.id,
                'product_uom_qty': water_qty,
                'product_uom': water_product.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': prod_loc.id,
                'company_id': self.env.company.id,
                'date': self.date or fields.Date.today(),
                'procure_method': 'make_to_stock',
            }))

        # Consume raw materials from Stock -> Production FIRST
        picking_raw = self.env['stock.picking'].create({
            'picking_type_id': int_type.id,
            'location_id': stock_loc.id,
            'location_dest_id': prod_loc.id,
            'move_ids': raw_moves,
        })
        for move in picking_raw.move_ids:
            move._set_quantity_done(move.product_uom_qty)
        picking_raw.button_validate()

        # Move intermediate(s) from Production -> destination SECOND
        dest_loc = stock_loc if self.destination_is_stock else buffer_loc
        picking = self.env['stock.picking'].create({
            'picking_type_id': int_type.id,
            'location_id': prod_loc.id,
            'location_dest_id': dest_loc.id,
            'move_ids': inter_moves,
        })
        for move in picking.move_ids:
            move._set_quantity_done(move.product_uom_qty)
        picking.button_validate()

        self.write({'picking_id': picking.id, 'state': 'confirmed'})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'material.transformation',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def action_cancel(self):
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(f'Cannot cancel a transformation in state "{self.state}". Only confirmed records can be canceled.')

        stock_loc = self.env['stock.location'].search([
            ('name', '=', 'Stock'),
        ], limit=1)
        buffer_loc = self.env['stock.location'].search([
            ('name', '=', 'Cultivation Buffer'),
        ], limit=1)
        prod_loc = self.env['stock.location'].search([
            ('usage', '=', 'production'),
        ], limit=1)

        if not all([stock_loc, buffer_loc, prod_loc]):
            raise UserError('Required locations not found for reverse move.')

        int_type = self.env.ref('stock.picking_type_internal', raise_if_not_found=False)
        if not int_type:
            int_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1)

        # Determine water product and qty used during confirm
        water_product = self.env['product.product'].search([('name', '=', 'Raw Water')], limit=1)
        water_qty = self._get_water_qty()

        secondary_qty = 0.0
        if self.secondary_intermediate_product_id and self.secondary_conversion_factor:
            secondary_qty = self.quantity * self.secondary_conversion_factor

        # 1. Reverse intermediate moves: Buffer -> Production
        inter_moves = [(0, 0, {
            'product_id': self.intermediate_product_id.id,
            'product_uom_qty': self.intermediate_qty,
            'product_uom': self.intermediate_product_id.uom_id.id,
            'location_id': buffer_loc.id,
            'location_dest_id': prod_loc.id,
            'company_id': self.env.company.id,
            'date': fields.Datetime.now(),
            'procure_method': 'make_to_stock',
        })]
        if secondary_qty > 0 and self.secondary_intermediate_product_id:
            inter_moves.append((0, 0, {
                'product_id': self.secondary_intermediate_product_id.id,
                'product_uom_qty': secondary_qty,
                'product_uom': self.secondary_intermediate_product_id.uom_id.id,
                'location_id': buffer_loc.id,
                'location_dest_id': prod_loc.id,
                'company_id': self.env.company.id,
                'date': fields.Datetime.now(),
                'procure_method': 'make_to_stock',
            }))

        # 2. Reverse raw material moves: Production -> Stock
        raw_source_loc = buffer_loc if self.source_is_buffer else stock_loc
        raw_moves = [(0, 0, {
            'product_id': self.product_id.id,
            'product_uom_qty': self.quantity,
            'product_uom': self.product_id.uom_id.id,
            'location_id': prod_loc.id,
            'location_dest_id': raw_source_loc.id,
            'company_id': self.env.company.id,
            'date': fields.Datetime.now(),
            'procure_method': 'make_to_stock',
        })]
        if water_qty > 0 and water_product:
            raw_moves.append((0, 0, {
                'product_id': water_product.id,
                'product_uom_qty': water_qty,
                'product_uom': water_product.uom_id.id,
                'location_id': prod_loc.id,
                'location_dest_id': stock_loc.id,
                'company_id': self.env.company.id,
                'date': fields.Datetime.now(),
                'procure_method': 'make_to_stock',
            }))

        # Execute reverse: intermediates Buffer -> Production FIRST
        picking_reverse_inter = self.env['stock.picking'].create({
            'picking_type_id': int_type.id,
            'location_id': buffer_loc.id,
            'location_dest_id': prod_loc.id,
            'move_ids': inter_moves,
        })
        for move in picking_reverse_inter.move_ids:
            move._set_quantity_done(move.product_uom_qty)
        picking_reverse_inter.button_validate()

        # Execute reverse: raw materials Production -> Stock SECOND
        picking_reverse_raw = self.env['stock.picking'].create({
            'picking_type_id': int_type.id,
            'location_id': prod_loc.id,
            'location_dest_id': raw_source_loc.id,
            'move_ids': raw_moves,
        })
        for move in picking_reverse_raw.move_ids:
            move._set_quantity_done(move.product_uom_qty)
        picking_reverse_raw.button_validate()

        self.write({'state': 'canceled', 'return_picking_id': picking_reverse_inter.id})
        return True
