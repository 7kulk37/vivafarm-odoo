from odoo import fields, models, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class Cultivation(models.Model):
    _name = 'vivafarm.cultivation'
    _description = 'Cultivation cycle - tracks seed to harvest'
    _order = 'id desc'

    name = fields.Char(
        string='Reference', copy=False,
        default=lambda self: 'Draft')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('germinated', 'Germinated'),
        ('transplanted', 'Transplanted'),
        ('harvested', 'Harvested'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ], string='Status', default='draft')

    # Seed input
    recipe_id = fields.Many2one(
        'vivafarm.recipe', string='Recipe',
        help='Select a recipe to auto-fill defaults')
    target_transplant_date = fields.Date(
        string='Target Transplant Date', readonly=True, store=True,
        compute='_compute_target_dates',
        help='Calculated from plant_date + recipe germinate_duration')
    target_harvest_date = fields.Date(
        string='Target Harvest Date', readonly=True, store=True,
        compute='_compute_target_dates',
        help='Calculated from plant_date + recipe total_grow_duration')
    plant_date = fields.Date(string='Plant Date', required=True)
    seed_lot_id = fields.Many2one('stock.lot', string='Seed Lot')
    seed_product_id = fields.Many2one(
        'product.product', string='Seed Product',
        related='seed_lot_id.product_id', readonly=True)
    grams_to_sow = fields.Float(string='Grams to Sow', default=0.5)
    grams_consumed = fields.Float(string='Grams Consumed', readonly=True)

    # Nutrient & acid products (set once at draft)
    nutrient_product_id = fields.Many2one(
        'product.product', string='Nutrient Product',
        domain="[('type', '=', 'consu')]",
        help='Nutrient product consumed during this cultivation cycle')
    acid_product_id = fields.Many2one(
        'product.product', string='Acid Product',
        domain="[('type', '=', 'consu')]",
        help='Acid product consumed during this cultivation cycle')

    # Computed totals from daily farm.input.log records
    total_nutrient_consumed = fields.Float(
        string='Total Nutrient (g)', readonly=True,
        compute='_compute_consumable_totals', store=False,
        help='Sum of nutrient adjustments from daily input logs linked to this batch')
    total_acid_consumed = fields.Float(
        string='Total Acid (ml)', readonly=True,
        compute='_compute_consumable_totals', store=False,
        help='Sum of acid adjustments from daily input logs linked to this batch')

    # Live plants
    crop_id = fields.Many2one(
        'product.product', string='Crop',
        domain="[('name', 'ilike', '(Live)')]")
    live_lot_id = fields.Many2one('stock.lot', string='Live Lot', readonly=True)
    target_plant_count = fields.Integer(string='Target Plants', default=240)
    plant_count = fields.Integer(string='Plants Created', readonly=True)

    # Locations
    nursery_id = fields.Many2one(
        'stock.location', string='Nursery',
        domain="[('usage', '=', 'internal'), ('name', 'ilike', 'Nursery')]")
    bench_id = fields.Many2one(
        'stock.location', string='Bench',
        domain="[('usage', '=', 'internal'), ('name', 'ilike', 'Bench')]")
    transplanted_date = fields.Date(string='Transplanted Date')
    transplant_amount = fields.Integer(string='Transplant Amount', default=240)

    # Harvest
    harvest_date = fields.Date(string='Harvest Date')
    packed_product_id = fields.Many2one(
        'product.product', string='Packed Product',
        domain="[('name', 'ilike', '(Packed)')]")
    packed_kg = fields.Float(string='Packed Kg')
    packed_lot_id = fields.Many2one('stock.lot', string='Packed Lot', readonly=True)
    spoilage_units = fields.Integer(string='Spoilage Units', default=0)

    # Dates
    germinated_date = fields.Datetime(string='Germinated Date', readonly=True)
    growing_date = fields.Datetime(string='Transplanted At', readonly=True)
    harvested_date = fields.Datetime(string='Harvested Date', readonly=True)
    done_date = fields.Datetime(string='Done Date', readonly=True)
    canceled_date = fields.Datetime(string='Canceled Date', readonly=True)

    # Stock moves
    plant_picking_id = fields.Many2one('stock.picking', string='Plant Picking', readonly=True)
    harvest_picking_id = fields.Many2one('stock.picking', string='Harvest Picking', readonly=True)

    # Observations log
    notes = fields.Text(string='Notes / Observations')

    # No constraints — duplicate live lot names allowed (trace by packed lot)

    @api.model
    def _next_reference(self):
        last = self.search([('name', '!=', 'Draft')], order='id desc', limit=1)
        if last and last.name and last.name.startswith('CUL-'):
            try:
                num = int(last.name.split('-')[1]) + 1
            except (IndexError, ValueError):
                num = 1
        else:
            num = 1
        return f'CUL-{num:03d}'

    @api.onchange('seed_lot_id')
    def _onchange_seed_lot(self):
        """Auto-fill crop and packed product from seed lot by name derivation."""
        if self.seed_lot_id and self.seed_lot_id.product_id:
            seed_name = self.seed_lot_id.product_id.name
            # Derive crop and packed names from seed name
            # e.g. "Seeds - Green Oak" → "Green Oak (Live)" / "Green Oak (Packed)"
            if seed_name and seed_name.startswith('Seeds - '):
                base = seed_name.replace('Seeds - ', '')
                live_name = f'{base} (Live)'
                packed_name = f'{base} (Packed)'
                live = self.env['product.product'].search([('name', '=', live_name)], limit=1)
                if live:
                    self.crop_id = live
                packed = self.env['product.product'].search([('name', '=', packed_name)], limit=1)
                if packed:
                    self.packed_product_id = packed

    @api.onchange('plant_date')
    def _onchange_plant_date(self):
        """No-op: plant date only affects live lot name, not cultivation reference."""
        pass

    @api.onchange('recipe_id')
    def _onchange_recipe(self):
        """Auto-fill all defaults from selected recipe."""
        if not self.recipe_id:
            return
        recipe = self.recipe_id
        self.crop_id = recipe.crop_id
        self.packed_product_id = recipe.packed_product_id
        self.nutrient_product_id = recipe.nutrient_product_id
        self.acid_product_id = recipe.acid_product_id
        self.grams_to_sow = recipe.grams_to_sow
        self.target_plant_count = recipe.target_plant_count
        self.transplant_amount = recipe.transplant_amount
        self.nursery_id = recipe.nursery_id
        # Auto-find a seed lot matching the recipe's seed product
        if recipe.seed_product_id and not self.seed_lot_id:
            lot = self.env['stock.lot'].search([
                ('product_id', '=', recipe.seed_product_id.id),
                ('product_qty', '>', 0),
            ], order='id asc', limit=1)
            if lot:
                self.seed_lot_id = lot.id

    @api.depends('plant_date', 'recipe_id')
    def _compute_target_dates(self):
        """Calculate target transplant and harvest dates from recipe durations."""
        for record in self:
            if not record.plant_date or not record.recipe_id:
                record.target_transplant_date = False
                record.target_harvest_date = False
                continue
            record.target_transplant_date = record.plant_date + timedelta(
                days=record.recipe_id.germinate_duration or 0)
            record.target_harvest_date = record.plant_date + timedelta(
                days=record.recipe_id.total_grow_duration or 0)

    @api.model_create_multi
    def create(self, vals_list):
        """Apply recipe defaults on create (onchange only fires in UI)."""
        for vals in vals_list:
            if vals.get('recipe_id'):
                recipe = self.env['vivafarm.recipe'].browse(vals['recipe_id'])
                if recipe:
                    if not vals.get('crop_id'):
                        vals['crop_id'] = recipe.crop_id.id
                    if not vals.get('packed_product_id'):
                        vals['packed_product_id'] = recipe.packed_product_id.id
                    if not vals.get('nutrient_product_id'):
                        vals['nutrient_product_id'] = recipe.nutrient_product_id.id
                    if not vals.get('acid_product_id'):
                        vals['acid_product_id'] = recipe.acid_product_id.id
                    if not vals.get('grams_to_sow'):
                        vals['grams_to_sow'] = recipe.grams_to_sow
                    if not vals.get('target_plant_count'):
                        vals['target_plant_count'] = recipe.target_plant_count
                    if not vals.get('transplant_amount'):
                        vals['transplant_amount'] = recipe.transplant_amount
                    if not vals.get('nursery_id'):
                        vals['nursery_id'] = recipe.nursery_id.id if recipe.nursery_id else False
                    if not vals.get('seed_lot_id') and recipe.seed_product_id:
                        lot = self.env['stock.lot'].search([
                            ('product_id', '=', recipe.seed_product_id.id),
                            ('product_qty', '>', 0),
                        ], order='id asc', limit=1)
                        if lot:
                            vals['seed_lot_id'] = lot.id
        return super(Cultivation, self).create(vals_list)

    # ── Computed totals from daily logs ──────────────

    def _compute_consumable_totals(self):
        """Sum nutrient/acid adjustments from farm.input.log linked to this batch."""
        for record in self:
            if not record.live_lot_id or not record.bench_id:
                record.total_nutrient_consumed = 0.0
                record.total_acid_consumed = 0.0
                continue
            logs = self.env['farm.input.log'].search([
                ('lot_id', '=', record.live_lot_id.id),
                ('bench_id', '=', record.bench_id.id),
                ('state', '=', 'confirmed'),
            ])
            record.total_nutrient_consumed = sum(
                l.nutrient_adjustment for l in logs)
            record.total_acid_consumed = sum(
                l.acid_adjustment for l in logs)

    # ── Actions ──────────────────────────────────────────

    def _get_production_loc(self):
        loc = self.env.ref('stock.location_production', raise_if_not_found=False)
        if not loc:
            loc = self.env['stock.location'].search([('usage', '=', 'production')], limit=1)
        return loc

    def _get_spoilage_loc(self):
        return self.env['stock.location'].search([
            ('name', '=', 'Spoilage'),
            ('location_id.name', '=', 'Stock'),
        ], limit=1)

    def _get_packed_loc(self):
        return self.env['stock.location'].search([
            ('name', '=', 'Packed Goods'),
        ], limit=1)

    def action_germinate(self):
        """Draft → Germinated: consume seeds, create live plants at nursery."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('Can only germinate in Draft state.')
        if not all([self.seed_lot_id, self.nursery_id, self.crop_id, self.plant_date]):
            # Auto-fill crop and packed from seed lot if missing
            if self.seed_lot_id and not self.crop_id:
                self._onchange_seed_lot()
            missing = []
            if not self.seed_lot_id: missing.append('seed_lot_id')
            if not self.nursery_id: missing.append('nursery_id')
            if not self.crop_id: missing.append('crop_id')
            if not self.plant_date: missing.append('plant_date')
            if missing:
                raise UserError(f'Missing fields: {", ".join(missing)}')

        seed_lot = self.seed_lot_id
        if seed_lot.product_qty < self.grams_to_sow:
            raise UserError(
                f'Not enough stock. Seed lot {seed_lot.name} has '
                f'{seed_lot.product_qty}g available, but {self.grams_to_sow}g requested.')

        # Live lot name: YY-WW format from plant date (duplicates allowed)
        live_lot_name = fields.Date.from_string(self.plant_date).strftime('%y%W')

        prod_loc = self._get_production_loc()

        # 1. Consume seeds: Nursery → Production
        seed_move_vals = {
            'product_id': seed_lot.product_id.id,
            'product_uom_qty': self.grams_to_sow,
            'product_uom': seed_lot.product_id.uom_id.id,
            'location_id': self.nursery_id.id,
            'location_dest_id': prod_loc.id,
            'company_id': self.env.company.id,
            'date': fields.Datetime.now(),
            'procure_method': 'make_to_stock',
            'move_line_ids': [(0, 0, {
                'product_id': seed_lot.product_id.id,
                'lot_id': seed_lot.id,
                'quantity': self.grams_to_sow,
                'product_uom_id': seed_lot.product_id.uom_id.id,
                'location_id': self.nursery_id.id,
                'location_dest_id': prod_loc.id,
            })],
        }

        # 2. Create live plants: Production → Nursery
        live_move_vals = {
            'product_id': self.crop_id.id,
            'product_uom_qty': self.target_plant_count,
            'product_uom': self.crop_id.uom_id.id,
            'location_id': prod_loc.id,
            'location_dest_id': self.nursery_id.id,
            'company_id': self.env.company.id,
            'date': fields.Datetime.now(),
            'procure_method': 'make_to_stock',
        }

        picking = self.env['stock.picking'].create({
            'picking_type_id': self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1).id,
            'location_id': self.nursery_id.id,
            'location_dest_id': self.nursery_id.id,
            'move_ids': [(0, 0, seed_move_vals), (0, 0, live_move_vals)],
        })

        # Create live lot using standard Odoo create (unique constraint already dropped)
        live_lot = self.env['stock.lot'].create({
            'name': live_lot_name,
            'product_id': self.crop_id.id,
            'company_id': self.env.company.id,
        })
        # Set x_seed_lot after creation
        live_lot.write({'x_seed_lot': seed_lot.name})

        # Add lot to live move line
        for move in picking.move_ids:
            if move.product_id == self.crop_id:
                self.env['stock.move.line'].create({
                    'move_id': move.id,
                    'picking_id': picking.id,
                    'product_id': self.crop_id.id,
                    'lot_id': live_lot.id,
                    'quantity': self.target_plant_count,
                    'product_uom_id': self.crop_id.uom_id.id,
                    'location_id': prod_loc.id,
                    'location_dest_id': self.nursery_id.id,
                })

        picking.button_validate()

        self.write({
            'state': 'germinated',
            'name': self._next_reference(),
            'live_lot_id': live_lot.id,
            'grams_consumed': self.grams_to_sow,
            'plant_count': self.target_plant_count,
            'germinated_date': fields.Datetime.now(),
            'plant_picking_id': picking.id,
        })

        return self._reopen()

    def action_grow(self):
        """Germinated → Growing: assign bench, move live plants."""
        self.ensure_one()
        if self.state != 'germinated':
            raise UserError('Can only grow from Germinated state.')
        if not self.bench_id:
            raise UserError('Select a bench location.')
        if not self.transplant_amount or self.transplant_amount <= 0:
            raise UserError('Transplant amount must be greater than 0.')

        prod_loc = self._get_production_loc()

        # Transfer live plants: Nursery → Bench
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1).id,
            'location_id': self.nursery_id.id,
            'location_dest_id': self.bench_id.id,
            'move_ids': [(0, 0, {
                'product_id': self.crop_id.id,
                'product_uom_qty': self.transplant_amount,
                'product_uom': self.crop_id.uom_id.id,
                'location_id': self.nursery_id.id,
                'location_dest_id': self.bench_id.id,
                'company_id': self.env.company.id,
                'date': fields.Datetime.now(),
                'procure_method': 'make_to_stock',
                'move_line_ids': [(0, 0, {
                    'product_id': self.crop_id.id,
                    'lot_id': self.live_lot_id.id,
                    'quantity': self.transplant_amount,
                    'product_uom_id': self.crop_id.uom_id.id,
                    'location_id': self.nursery_id.id,
                    'location_dest_id': self.bench_id.id,
                })],
            })],
        })

        picking.button_validate()

        self.write({
            'state': 'transplanted',
            'growing_date': fields.Datetime.now(),
            'transplanted_date': self.transplanted_date or fields.Date.today(),
        })

        return self._reopen()

    def action_harvest(self):
        """Growing → Harvested: record harvest data (no stock moves yet)."""
        self.ensure_one()
        if self.state != 'transplanted':
            raise UserError('Can only harvest from Growing state.')
        if not self.harvest_date:
            raise UserError('Enter a harvest date.')
        if not self.packed_product_id:
            raise UserError('Select a packed product.')
        if not self.packed_kg:
            raise UserError('Enter packed kg.')

        self.write({
            'state': 'harvested',
            'harvested_date': fields.Datetime.now(),
        })

        return self._reopen()

    def action_done(self):
        """Harvested → Done: execute stock moves (packed → WH/Stock, spoilage → Spoilage)."""
        self.ensure_one()
        if self.state != 'harvested':
            raise UserError('Can only mark Done from Harvested state.')

        # Recompute consumable totals from daily logs before creating moves
        self._compute_consumable_totals()

        live_lot = self.live_lot_id
        total_units = int(live_lot.product_qty)
        if total_units <= 0:
            raise UserError(f'Lot {live_lot.name} has no stock to harvest.')

        prod_loc = self._get_production_loc()
        spoilage_loc = self._get_spoilage_loc()
        packed_loc = self._get_packed_loc()

        source_loc = self.bench_id or self.nursery_id

        # Build packed lot name: SeedLot-LiveLot-Location
        seed_code = self.seed_lot_id.name
        live_code = self.live_lot_id.name
        nursery_code = self.nursery_id.name.split()[0] if self.nursery_id.name else ''
        bench_code = self.bench_id.name.split()[0] if self.bench_id else ''
        packed_lot_name = f'{seed_code}-{live_code}-{nursery_code}{bench_code}'

        # 1. Consume live plants: source → Production
        live_move_vals = {
            'product_id': live_lot.product_id.id,
            'product_uom_qty': total_units,
            'product_uom': live_lot.product_id.uom_id.id,
            'location_id': source_loc.id,
            'location_dest_id': prod_loc.id,
            'company_id': self.env.company.id,
            'date': fields.Datetime.now(),
            'procure_method': 'make_to_stock',
            'move_line_ids': [(0, 0, {
                'product_id': live_lot.product_id.id,
                'lot_id': live_lot.id,
                'quantity': total_units,
                'product_uom_id': live_lot.product_id.uom_id.id,
                'location_id': source_loc.id,
                'location_dest_id': prod_loc.id,
            })],
        }

        # 2. Create packed goods: Production → Packed Goods
        packed_move_vals = {
            'product_id': self.packed_product_id.id,
            'product_uom_qty': self.packed_kg,
            'product_uom': self.packed_product_id.uom_id.id,
            'location_id': prod_loc.id,
            'location_dest_id': packed_loc.id,
            'company_id': self.env.company.id,
            'date': fields.Datetime.now(),
            'procure_method': 'make_to_stock',
            'move_line_ids': [(0, 0, {
                'product_id': self.packed_product_id.id,
                'quantity': self.packed_kg,
                'product_uom_id': self.packed_product_id.uom_id.id,
                'location_id': prod_loc.id,
                'location_dest_id': packed_loc.id,
            })],
        }

        moves = [live_move_vals, packed_move_vals]

        # 3. If spoilage: move from source → Spoilage
        if self.spoilage_units > 0:
            spoilage_move_vals = {
                'product_id': live_lot.product_id.id,
                'product_uom_qty': self.spoilage_units,
                'product_uom': live_lot.product_id.uom_id.id,
                'location_id': source_loc.id,
                'location_dest_id': spoilage_loc.id,
                'company_id': self.env.company.id,
                'date': fields.Datetime.now(),
                'procure_method': 'make_to_stock',
                'move_line_ids': [(0, 0, {
                    'product_id': live_lot.product_id.id,
                    'lot_id': live_lot.id,
                    'quantity': self.spoilage_units,
                    'product_uom_id': live_lot.product_id.uom_id.id,
                    'location_id': source_loc.id,
                    'location_dest_id': spoilage_loc.id,
                })],
            }
            moves.append(spoilage_move_vals)

        # 4. Consume nutrient: WH/Stock → Production
        stock_loc = self.env.ref('stock.stock_location_stock')
        if self.nutrient_product_id and self.total_nutrient_consumed > 0:
            moves.append({
                'product_id': self.nutrient_product_id.id,
                'product_uom_qty': self.total_nutrient_consumed,
                'product_uom': self.nutrient_product_id.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': prod_loc.id,
                'company_id': self.env.company.id,
                'date': fields.Datetime.now(),
                'procure_method': 'make_to_stock',
            })

        # 5. Consume acid: WH/Stock → Production
        if self.acid_product_id and self.total_acid_consumed > 0:
            moves.append({
                'product_id': self.acid_product_id.id,
                'product_uom_qty': self.total_acid_consumed,
                'product_uom': self.acid_product_id.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': prod_loc.id,
                'company_id': self.env.company.id,
                'date': fields.Datetime.now(),
                'procure_method': 'make_to_stock',
            })

        picking = self.env['stock.picking'].create({
            'picking_type_id': self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1).id,
            'location_id': source_loc.id,
            'location_dest_id': prod_loc.id,
            'move_ids': [(0, 0, m) for m in moves],
        })

        picking.button_validate()

        # Create packed lot using standard Odoo create (unique constraint already dropped)
        packed_lot = self.env['stock.lot'].create({
            'name': packed_lot_name,
            'product_id': self.packed_product_id.id,
            'company_id': self.env.company.id,
        })

        self.write({
            'state': 'done',
            'done_date': fields.Datetime.now(),
            'packed_lot_id': packed_lot.id,
            'harvest_picking_id': picking.id,
        })

        return self._reopen()

    def action_cancel(self):
        """Cancel from any state. Returns seeds if germinated/growing."""
        self.ensure_one()
        if self.state == 'done':
            raise UserError('Cannot cancel a completed cultivation.')

        # If seeds were consumed, return them
        if self.state in ('germinated', 'transplanted') and self.plant_picking_id:
            prod_loc = self._get_production_loc()

            # Reverse: move seeds back from Production → Nursery
            return_picking = self.env['stock.picking'].create({
                'picking_type_id': self.env['stock.picking.type'].search([
                    ('code', '=', 'internal')
                ], limit=1).id,
                'location_id': prod_loc.id,
                'location_dest_id': self.nursery_id.id,
                'move_ids': [(0, 0, {
                    'product_id': self.seed_lot_id.product_id.id,
                    'product_uom_qty': self.grams_consumed,
                    'product_uom': self.seed_lot_id.product_id.uom_id.id,
                    'location_id': prod_loc.id,
                    'location_dest_id': self.nursery_id.id,
                    'company_id': self.env.company.id,
                    'date': fields.Datetime.now(),
                    'procure_method': 'make_to_stock',
                    'move_line_ids': [(0, 0, {
                        'product_id': self.seed_lot_id.product_id.id,
                        'lot_id': self.seed_lot_id.id,
                        'quantity': self.grams_consumed,
                        'product_uom_id': self.seed_lot_id.product_id.uom_id.id,
                        'location_id': prod_loc.id,
                        'location_dest_id': self.nursery_id.id,
                    })],
                })],
            })
            return_picking.button_validate()

        self.write({
            'state': 'canceled',
            'canceled_date': fields.Datetime.now(),
        })

        return self._reopen()

    def unlink(self):
        """Block deletion of non-draft cultivations."""
        for record in self:
            if record.state != 'draft':
                raise UserError(
                    f'Cannot delete cultivation {record.name or "Draft"} '
                    f'in state "{record.state}". Cancel it first.')
        return super(Cultivation, self).unlink()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'vivafarm.cultivation',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
