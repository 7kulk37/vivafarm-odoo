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
        readonly=True,
        help='Seed product auto-filled from recipe')
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
        'farm.location', string='Nursery',
        domain="[('location_type', '=', 'nursery')]")
    bench_id = fields.Many2one(
        'farm.location', string='Bench',
        domain="[('location_type', '=', 'bench')]")
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
    packed_picking_id = fields.Many2one('stock.picking', string='Packed Picking', readonly=True)

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

    @api.onchange('recipe_id')
    def _onchange_recipe(self):
        """Auto-fill all defaults from selected recipe."""
        if not self.recipe_id:
            return
        recipe = self.recipe_id
        self.seed_product_id = recipe.seed_product_id
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
                    if not vals.get('seed_product_id'):
                        vals['seed_product_id'] = recipe.seed_product_id.id if recipe.seed_product_id else False
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
                        ], order='id asc', limit=1)
                        if lot:
                            vals['seed_lot_id'] = lot.id
        return super(Cultivation, self).create(vals_list)

    # ── Computed totals from daily logs ──────────────

    def _compute_consumable_totals(self):
        """Sum nutrient/acid adjustments from farm.input.log linked to this batch."""
        for record in self:
            if not record.live_lot_id:
                record.total_nutrient_consumed = 0.0
                record.total_acid_consumed = 0.0
                continue
            logs = self.env['farm.input.log'].search([
                ('lot_id', '=', record.live_lot_id.id),
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

    def _get_stock_loc(self):
        return self.env['stock.location'].search([
            ('name', '=', 'Stock'),
        ], limit=1)

    def _get_spoilage_loc(self):
        return self.env['stock.location'].search([
            ('name', '=', 'Spoilage'),
            ('location_id.name', '=', 'Stock'),
        ], limit=1)

    def _get_packed_loc(self):
        return self.env['stock.location'].search([
            ('name', '=', 'Packed Goods'),
        ], limit=1)

    def _get_farm_stock_loc(self, farm_loc=None):
        """All cultivation stock moves now use the main WH/Stock location.

        Farm.location records are labels for input logs and cultivation forms only.
        """
        return self._get_stock_loc()

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
        # For consu products in Odoo 19, lots exist but move lines aren't created.
        # Just verify the lot was created during receive.
        if not seed_lot.exists():
            raise UserError(
                f'Seed lot {seed_lot.name} not found. Receive seeds first.')

        # Live lot name: YY-WW format from plant date (duplicates allowed)
        live_lot_name = fields.Date.from_string(self.plant_date).strftime('%y%W')

        prod_loc = self._get_production_loc()

        # 1. Consume seeds: Stock → Production
        seed_move_vals = {
            'product_id': seed_lot.product_id.id,
            'product_uom_qty': self.grams_to_sow,
            'product_uom': seed_lot.product_id.uom_id.id,
            'location_id': self._get_stock_loc().id,
            'location_dest_id': prod_loc.id,
            'company_id': self.env.company.id,
            'date': fields.Datetime.now(),
            'procure_method': 'make_to_stock',
            'move_line_ids': [(0, 0, {
                'product_id': seed_lot.product_id.id,
                'lot_id': seed_lot.id,
                'quantity': self.grams_to_sow,
                'product_uom_id': seed_lot.product_id.uom_id.id,
                'location_id': self._get_stock_loc().id,
                'location_dest_id': prod_loc.id,
            })],
        }

        # 2. Create live plants: Production → WH/Stock
        stock_loc = self._get_stock_loc()
        live_move_vals = {
            'product_id': self.crop_id.id,
            'product_uom_qty': self.target_plant_count,
            'product_uom': self.crop_id.uom_id.id,
            'location_id': prod_loc.id,
            'location_dest_id': stock_loc.id,
            'company_id': self.env.company.id,
            'date': fields.Datetime.now(),
            'procure_method': 'make_to_stock',
        }

        int_type = self.env.ref('stock.picking_type_internal', raise_if_not_found=False)
        if not int_type:
            int_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1)

        picking = self.env['stock.picking'].create({
            'picking_type_id': int_type.id,
            'location_id': stock_loc.id,
            'location_dest_id': stock_loc.id,
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
                    'location_dest_id': stock_loc.id,
                })

        picking.button_validate()

        # Assign seed cost to the live plant product so it carries cost through cultivation.
        # Cost per live plant unit = total seed value / number of live plants produced.
        seed_move = next((m for m in picking.move_ids if m.product_id == seed_lot.product_id), None)
        live_move = next((m for m in picking.move_ids if m.product_id == self.crop_id), None)
        if seed_move and live_move and live_move.product_uom_qty:
            unit_cost = (seed_move.value or 0.0) / live_move.product_uom_qty
            if unit_cost:
                self.crop_id.product_tmpl_id.standard_price = unit_cost

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
        stock_loc = self._get_stock_loc()

        # Transfer live plants: WH/Stock → WH/Stock (state change only, no per-location tracking)
        int_type = self.env.ref('stock.picking_type_internal', raise_if_not_found=False)
        if not int_type:
            int_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1)

        picking = self.env['stock.picking'].create({
            'picking_type_id': int_type.id,
            'location_id': stock_loc.id,
            'location_dest_id': stock_loc.id,
            'move_ids': [(0, 0, {
                'product_id': self.crop_id.id,
                'product_uom_qty': self.transplant_amount,
                'product_uom': self.crop_id.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': stock_loc.id,
                'company_id': self.env.company.id,
                'date': fields.Datetime.now(),
                'procure_method': 'make_to_stock',
                'move_line_ids': [(0, 0, {
                    'product_id': self.crop_id.id,
                    'lot_id': self.live_lot_id.id,
                    'quantity': self.transplant_amount,
                    'product_uom_id': self.crop_id.uom_id.id,
                    'location_id': stock_loc.id,
                    'location_dest_id': stock_loc.id,
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
            raise UserError('Can only harvest from Transplanted state.')
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

    def _compute_labor_share(self):
        """Compute this cultivation's share of the daily labor rate.

        For each day between plant_date and harvest_date, find how many
        cultivations are active (not draft/canceled), and split the daily
        rate equally among them.
        """
        self.ensure_one()
        labor_product = self.env['product.product'].search([
            ('product_tmpl_id.name', '=', 'Direct Labor Allocation')
        ], limit=1)
        if not labor_product:
            return 0.0
        daily_rate = labor_product.standard_price or 0.0
        if not daily_rate:
            return 0.0
        start = self.plant_date
        end = self.harvest_date
        if not start or not end:
            return 0.0
        total = 0.0
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            active = self.env['vivafarm.cultivation'].search_count([
                ('state', 'not in', ['draft', 'canceled']),
                ('plant_date', '<=', day),
                ('harvest_date', '>=', day),
            ])
            total += daily_rate / max(active, 1)
        return total

    def action_done(self):
        """Harvested → Done: execute stock moves (packed → WH/Stock, spoilage → Spoilage)."""
        self.ensure_one()
        if self.state != 'harvested':
            raise UserError('Can only mark Done from Harvested state.')

        # Recompute consumable totals from daily logs before creating moves
        self._compute_consumable_totals()

        live_lot = self.live_lot_id
        # For consu products, product_qty is 0 — use transplant_amount instead
        total_units = int(live_lot.product_qty) if live_lot.product_qty else int(self.transplant_amount or 0)
        if total_units <= 0:
            raise UserError(f'No stock to harvest. Lot {live_lot.name} has no quantity and transplant_amount is not set.')

        prod_loc = self._get_production_loc()
        spoilage_loc = self._get_spoilage_loc()
        packed_loc = self._get_packed_loc()
        stock_loc = self._get_stock_loc()

        # Build packed lot name: SeedLot-LiveLot-Location
        seed_code = self.seed_lot_id.name
        live_code = self.live_lot_id.name
        nursery_code = self.nursery_id.name.split()[0] if self.nursery_id.name else ''
        bench_code = self.bench_id.name.split()[0] if self.bench_id else ''
        packed_lot_name = f'{seed_code}-{live_code}-{nursery_code}{bench_code}'

        # 1. Consume live plants: WH/Stock → Production
        live_move_vals = {
            'product_id': live_lot.product_id.id,
            'product_uom_qty': total_units,
            'product_uom': live_lot.product_id.uom_id.id,
            'location_id': stock_loc.id,
            'location_dest_id': prod_loc.id,
            'company_id': self.env.company.id,
            'date': fields.Datetime.now(),
            'procure_method': 'make_to_stock',
            'move_line_ids': [(0, 0, {
                'product_id': live_lot.product_id.id,
                'lot_id': live_lot.id,
                'quantity': total_units,
                'product_uom_id': live_lot.product_id.uom_id.id,
                'location_id': stock_loc.id,
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

        # 3. If spoilage: move from WH/Stock → Spoilage
        if self.spoilage_units > 0:
            spoilage_move_vals = {
                'product_id': live_lot.product_id.id,
                'product_uom_qty': self.spoilage_units,
                'product_uom': live_lot.product_id.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': spoilage_loc.id,
                'company_id': self.env.company.id,
                'date': fields.Datetime.now(),
                'procure_method': 'make_to_stock',
                'move_line_ids': [(0, 0, {
                    'product_id': live_lot.product_id.id,
                    'lot_id': live_lot.id,
                    'quantity': self.spoilage_units,
                    'product_uom_id': live_lot.product_id.uom_id.id,
                    'location_id': stock_loc.id,
                    'location_dest_id': spoilage_loc.id,
                })],
            }
            moves.append(spoilage_move_vals)

        # 4. Consume nutrient: WH/Stock → Production (input logs are in ml, product UoM is L)
        stock_loc = self._get_stock_loc()
        if self.nutrient_product_id and self.total_nutrient_consumed > 0:
            moves.append({
                'product_id': self.nutrient_product_id.id,
                'product_uom_qty': self.total_nutrient_consumed / 1000.0,
                'product_uom': self.nutrient_product_id.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': prod_loc.id,
                'company_id': self.env.company.id,
                'date': fields.Datetime.now(),
                'procure_method': 'make_to_stock',
            })

        # 5. Consume acid: WH/Stock → Production (input logs are in ml, product UoM is L)
        if self.acid_product_id and self.total_acid_consumed > 0:
            moves.append({
                'product_id': self.acid_product_id.id,
                'product_uom_qty': self.total_acid_consumed / 1000.0,
                'product_uom': self.acid_product_id.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': prod_loc.id,
                'company_id': self.env.company.id,
                'date': fields.Datetime.now(),
                'procure_method': 'make_to_stock',
            })

        # 6. Consume direct labor allocation split by active cultivations per day
        labor_product = self.env['product.product'].search([
            ('product_tmpl_id.name', '=', 'Direct Labor Allocation')
        ], limit=1)
        labor_share = self._compute_labor_share()
        original_labor_price = 0.0
        if labor_product and labor_share > 0:
            start_date = self.plant_date or (self.germinated_date.date() if self.germinated_date else None)
            end_date = self.harvest_date or (self.harvested_date.date() if self.harvested_date else None)
            if start_date and end_date:
                labor_days = (end_date - start_date).days + 1
                if labor_days > 0:
                    unit_labor_price = labor_share / labor_days
                    # Odoo 19 stock move value uses product.standard_price at validation time,
                    # so temporarily set it to the per-day share for this batch.
                    original_labor_price = labor_product.product_tmpl_id.standard_price
                    labor_product.product_tmpl_id.standard_price = unit_labor_price
                    moves.append({
                        'product_id': labor_product.id,
                        'product_uom_qty': labor_days,
                        'product_uom': labor_product.uom_id.id,
                        'location_id': stock_loc.id,
                        'location_dest_id': prod_loc.id,
                        'company_id': self.env.company.id,
                        'date': fields.Datetime.now(),
                        'procure_method': 'make_to_stock',
                    })

        int_type = self.env.ref('stock.picking_type_internal', raise_if_not_found=False)
        if not int_type:
            int_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1)

        # Split into two pickings to avoid destination mismatch:
        # Picking 1: consume live + nutrient + acid (WH/Stock → Production)
        # Picking 2: create packed + spoilage (Production → destination)
        consume_moves = [m for m in moves if m['location_dest_id'] == prod_loc.id]
        produce_moves = [m for m in moves if m['location_id'] == prod_loc.id]

        picking = False
        total_input_cost = 0.0
        if consume_moves:
            picking = self.env['stock.picking'].create({
                'picking_type_id': int_type.id,
                'location_id': stock_loc.id,
                'location_dest_id': prod_loc.id,
                'move_ids': [(0, 0, m) for m in consume_moves],
            })
            for move in picking.move_ids:
                move._set_quantity_done(move.product_uom_qty)
            picking.button_validate()
            # Capture actual input cost from consumed move values
            total_input_cost = sum(move.value for move in picking.move_ids)

        if produce_moves:
            produce_dest = packed_loc
            if self.spoilage_units > 0:
                produce_dest = prod_loc
            picking2 = self.env['stock.picking'].create({
                'picking_type_id': int_type.id,
                'location_id': prod_loc.id,
                'location_dest_id': produce_dest.id,
                'move_ids': [(0, 0, m) for m in produce_moves],
            })
            for move in picking2.move_ids:
                move._set_quantity_done(move.product_uom_qty)

            # Do NOT assign unit cost or create stock valuation AM here.
            # FG uses standard cost; the exact batch cost is set below after
            # the WIP-FG journal entry is created, ensuring deliveries use that
            # exact cost and 113100 has no rounding mismatch.
            picking2.button_validate()
            if not picking:
                picking = picking2

        # Restore Direct Labor Allocation standard_price if we changed it
        if original_labor_price:
            labor_product.product_tmpl_id.standard_price = original_labor_price

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
            'packed_picking_id': picking2.id if produce_moves else False,
        })

        # Thai accounting: transfer the EXACT WIP balance for this batch to FG.
        # _create_wip_to_fg_entry reads the actual 113400 lines caused by this
        # batch's pickings and posts the opposite amount, so 113400 ends at zero.
        # We set the packed product's standard_price to the exact WIP-FG per-kg
        # so that standard-cost deliveries and COGS match the batch cost exactly.
        wip_fg_move = self._create_wip_to_fg_entry(None)
        if wip_fg_move:
            wip_fg_value = sum(l.debit for l in wip_fg_move.line_ids if l.account_id.code == '113100')
            unit_cost = wip_fg_value / self.packed_kg if self.packed_kg else 0.0
            # Set standard price on the product template (Odoo 19 standard cost).
            # This ensures outgoing moves created right after this harvest use
            # this exact unit cost. Because standard_price is global, deliveries
            # from older lots may use a later harvest's price; _balance_fg_for_batch
            # corrects any resulting 113100 residual per batch.
            self.packed_product_id.product_tmpl_id.standard_price = unit_cost

        return self._reopen()

    def action_balance_fg(self):
        """Post a balancing JE so that net 113100 impact of this batch is zero.

        When FG uses standard cost, Odoo's single standard_price per product
        template can cause deliveries of this batch's lot to be costed at a
        different batch's price. After all deliveries/spoilage for this batch
        are done, read the actual 113100 lines caused by this batch's WIP-FG
        entry and its packed lot's outgoing moves, then post the difference
        to a COGS/FG adjustment account. This is only used by demo scripts for
        exact-zero 113100.
        """
        self.ensure_one()
        if not self.packed_lot_id:
            return self.env['account.move']

        fg_acc = self.env['account.account'].search([('code', '=', '113100')], limit=1)
        cogs_acc = self.env['account.account'].search([('code', '=', '511100')], limit=1)
        if not fg_acc or not cogs_acc:
            return self.env['account.move']

        ref = f'FG-BAL-{self.id}'
        existing = self.env['account.move'].search([('ref', '=', ref)], limit=1)
        if existing:
            return existing

        # 113100 debit from WIP-FG entry
        wipfg = sum((l.debit - l.credit) for l in self.env['account.move.line'].search([
            ('move_id.ref', '=', f'WIP-FG-{self.id}'),
            ('account_id.code', '=', '113100'),
            ('parent_state', '=', 'posted'),
        ]))

        # 113100 credit from outgoing moves of this lot
        out_moves = self.env['stock.move'].search([
            ('product_id', '=', self.packed_product_id.id),
            ('state', '=', 'done'),
            ('move_line_ids.lot_id', '=', self.packed_lot_id.id),
        ])
        out_value = sum(m.value for m in out_moves)
        scrap_moves = self.env['stock.move'].search([
            ('product_id', '=', self.packed_product_id.id),
            ('state', '=', 'done'),
            ('location_dest_id.scrap_location', '=', True),
            ('move_line_ids.lot_id', '=', self.packed_lot_id.id),
        ])
        scrap_value = sum(m.value for m in scrap_moves)

        # Net 113100 impact for this batch
        fg_net = wipfg - out_value - scrap_value
        if abs(fg_net) < 0.005:
            return self.env['account.move']

        stock_journal = self.env.company.account_stock_journal_id
        if not stock_journal:
            return self.env['account.move']

        # If fg_net > 0, too much Dr 113100; credit 113100, debit COGS (we over-costed).
        # If fg_net < 0, too much Cr 113100; debit 113100, credit COGS (we under-costed).
        if fg_net > 0:
            line_ids = [
                (0, 0, {'account_id': cogs_acc.id, 'name': f'FG balance: {self.name}', 'debit': fg_net, 'credit': 0}),
                (0, 0, {'account_id': fg_acc.id, 'name': f'FG balance: {self.name}', 'debit': 0, 'credit': fg_net}),
            ]
        else:
            line_ids = [
                (0, 0, {'account_id': fg_acc.id, 'name': f'FG balance: {self.name}', 'debit': -fg_net, 'credit': 0}),
                (0, 0, {'account_id': cogs_acc.id, 'name': f'FG balance: {self.name}', 'debit': 0, 'credit': -fg_net}),
            ]
        move = self.env['account.move'].create({
            'ref': ref,
            'journal_id': stock_journal.id,
            'date': fields.Date.today(),
            'line_ids': line_ids,
        })
        move.action_post()
        return move

    def _get_batch_wip_delta(self):
        """Net change to WIP account caused by this cultivation batch.

        We sum the stock move values by direction:
        - Moves INTO Production from an internal location increase WIP (+)
        - Moves OUT OF Production to an internal/packed location decrease WIP (-)
        This avoids double-counting when Odoo groups multiple moves into one
        account move per picking.
        """
        self.ensure_one()
        delta = 0.0
        for pick in (self.plant_picking_id, self.harvest_picking_id, self.packed_picking_id):
            if not pick:
                continue
            for move in pick.move_ids:
                if move.state != 'done':
                    continue
                if move.location_id.usage == 'internal' and move.location_dest_id.usage == 'production':
                    delta += move.value
                elif move.location_id.usage == 'production' and move.location_dest_id.usage in ('internal', 'internal'):
                    # Packed goods location has usage='internal' as well; treat any
                    # production -> internal as WIP decrease.
                    delta -= move.value
        return delta

    def _create_wip_to_fg_entry(self, cost):
        """Create a posted JE that brings the batch's net WIP balance to zero.

        Option B: instead of trusting move.value rounding, we read the actual
        113400 balance caused by this batch's pickings and post the exact
        opposite amount to FG. This guarantees 113400 is zero for the batch.
        Idempotent — skips if entry already exists for this cultivation.
        """
        self.ensure_one()
        ref = f'WIP-FG-{self.id}'
        existing = self.env['account.move'].search([
            ('ref', '=', ref),
        ], limit=1)
        if existing:
            return existing

        fg_acc = self.packed_product_id._get_product_accounts()['stock_valuation']
        wip_cat = self.env['product.category'].search([('name', '=', 'WIP')], limit=1)
        wip_acc = wip_cat.property_stock_valuation_account_id if wip_cat else False
        if not fg_acc or not wip_acc:
            return self.env['account.move']

        # Compute actual 113400 balance from this batch's pickings.
        refs = []
        for pick in (self.plant_picking_id, self.harvest_picking_id, self.packed_picking_id):
            if pick:
                refs.append(pick.name)
        amls = self.env['account.move.line'].search([
            ('account_id', '=', wip_acc.id),
            ('parent_state', '=', 'posted'),
            ('move_id.ref', 'in', refs),
        ])
        wip_net = sum(amls.mapped('debit')) - sum(amls.mapped('credit'))
        if abs(wip_net) < 0.005:
            return self.env['account.move']

        # Post Dr FG / Cr WIP for the exact net amount.
        stock_journal = self.env.company.account_stock_journal_id
        if not stock_journal:
            return self.env['account.move']

        move = self.env['account.move'].create({
            'ref': ref,
            'journal_id': stock_journal.id,
            'date': fields.Date.today(),
            'line_ids': [(0, 0, {
                'account_id': fg_acc.id,
                'name': f'WIP→FG transfer: {self.name}',
                'debit': wip_net,
                'credit': 0,
            }), (0, 0, {
                'account_id': wip_acc.id,
                'name': f'WIP→FG transfer: {self.name}',
                'debit': 0,
                'credit': wip_net,
            })],
        })
        move.action_post()
        return move

    def action_cancel(self):
        """Cancel from any state. Returns seeds if germinated/growing."""
        self.ensure_one()
        if self.state == 'done':
            raise UserError('Cannot cancel a completed cultivation.')

        # If seeds were consumed, return them
        if self.state in ('germinated', 'transplanted') and self.plant_picking_id:
            prod_loc = self._get_production_loc()
            stock_loc = self._get_stock_loc()

            # Reverse: move seeds back from Production → WH/Stock
            return_picking = self.env['stock.picking'].create({
                'picking_type_id': self.env['stock.picking.type'].search([
                    ('code', '=', 'internal')
                ], limit=1).id,
                'location_id': prod_loc.id,
                'location_dest_id': stock_loc.id,
                'move_ids': [(0, 0, {
                    'product_id': self.seed_lot_id.product_id.id,
                    'product_uom_qty': self.grams_consumed,
                    'product_uom': self.seed_lot_id.product_id.uom_id.id,
                    'location_id': prod_loc.id,
                    'location_dest_id': stock_loc.id,
                    'company_id': self.env.company.id,
                    'date': fields.Datetime.now(),
                    'procure_method': 'make_to_stock',
                    'move_line_ids': [(0, 0, {
                        'product_id': self.seed_lot_id.product_id.id,
                        'lot_id': self.seed_lot_id.id,
                        'quantity': self.grams_consumed,
                        'product_uom_id': self.seed_lot_id.product_id.uom_id.id,
                        'location_id': prod_loc.id,
                        'location_dest_id': stock_loc.id,
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
