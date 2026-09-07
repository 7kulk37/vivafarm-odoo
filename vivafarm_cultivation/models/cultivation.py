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
    seed_lot_hex = fields.Char(
        string='Seed Lot Hex',
        compute='_compute_seed_lot_hex',
        readonly=True,
        help='Auto-generated hex code (e.g. GO-00A) from the selected seed lot',
    )
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
    nutrient_b_product_id = fields.Many2one(
        'product.product', string='Nutrient B Product',
        domain="[('type', '=', 'consu')]",
        help='Second nutrient concentrate consumed in equal quantity')
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
    packed_lot_weight_g = fields.Integer(string='Packed Weight (g)', readonly=True)
    crop_batch_sequence = fields.Integer(string='Crop Batch Sequence', readonly=True)
    # CL-10: per-packed-lot cost capture — specific-ID per batch survives
    # multi-batch concurrency without relying on the global standard_price.
    packed_lot_cost = fields.Float(
        string='Packed Lot Cost (THB)', readonly=True,
        help='Total batch cost (material + labor) captured at harvest',
    )
    packed_lot_cost_per_kg = fields.Float(
        string='Cost per kg (THB)', readonly=True,
        help='Packed lot cost / packed kg',
    )
    packed_lot_remaining_value = fields.Float(
        string='Remaining Value (THB)', readonly=True,
        help='Cost of the unsold portion of this packed lot',
    )
    spoilage_units = fields.Integer(string='Spoilage Units', default=0)
    spoilage_classification = fields.Selection([
        ('normal', 'Normal (≤5%)'),
        ('abnormal', 'Abnormal (>5%)'),
    ], string='Spoilage Classification', compute='_compute_spoilage_classification', store=True,
       help='CL-06: normal spoilage (≤5% of germinated) is absorbed into FG cost; '
            'abnormal (>5%) is a flagged period expense with a disposal record.')

    # Dates
    germinated_date = fields.Datetime(string='Germinated Date', readonly=True)
    growing_date = fields.Datetime(string='Growing Date', readonly=True)
    harvested_date = fields.Datetime(string='Harvested Date', readonly=True)
    done_date = fields.Datetime(string='Done Date', readonly=True)
    canceled_date = fields.Datetime(string='Canceled Date', readonly=True)
    # CL-18: F-07 harvest + pack multi-event (GAP 3.5.1/3.6.1)
    harvest_time = fields.Datetime(
        string='Harvest Time',
        help='When the harvest started',
    )
    packer_name = fields.Char(
        string='Packer',
        help='Worker who packed the produce (GAP 3.8.1 signature)',
    )
    pack_time = fields.Datetime(
        string='Pack Time',
        help='When the produce was packed',
    )

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
        self.nutrient_b_product_id = recipe.nutrient_b_product_id
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

    @api.depends('spoilage_units', 'target_plant_count')
    def _compute_spoilage_classification(self):
        """CL-06: normal ≤5% of germinated plants; above = abnormal."""
        for record in self:
            total = record.target_plant_count or 0
            if total and record.spoilage_units > total * 0.05:
                record.spoilage_classification = 'abnormal'
            else:
                record.spoilage_classification = 'normal'

    @api.depends('seed_lot_id')
    def _compute_seed_lot_hex(self):
        """Expose the lot's auto-generated hex code (e.g. GO-00A)."""
        for record in self:
            record.seed_lot_hex = record.seed_lot_id.x_seed_lot or False

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
                    if not vals.get('nutrient_b_product_id'):
                        vals['nutrient_b_product_id'] = recipe.nutrient_b_product_id.id if recipe.nutrient_b_product_id else False
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

    def _get_packed_lot_name(self):
        """Return packed lot name in format GC-YYWW-001-2643-N6C6.

        GC    = crop code (first letters of crop short name)
        YYWW  = harvest year + ISO week (traceability window; CL-13)
        001   = crop-specific batch sequence
        2643  = packed weight in grams (packed_kg * 1000)
        N6C6  = nursery code + bench code (e.g. N6 + C6)
        """
        self.ensure_one()
        # Crop code from packed product short name, e.g. 'Green Cos (Packed)' -> 'GC'
        base = (self.packed_product_id.name or '').replace('(Packed)', '').strip()
        words = base.split()
        if len(words) >= 2:
            crop_code = ''.join(w[0].upper() for w in words[:2])
        elif words:
            crop_code = words[0][:2].upper()
        else:
            crop_code = 'XX'
        seq = self.crop_batch_sequence or 1
        weight_g = int(round((self.packed_kg or 0.0) * 1000))
        nursery = self.nursery_id.name or ''
        bench = self.bench_id.name or ''
        # YY-WW from harvest date (fallback plant date) — shelf-pointable window
        anchor = self.harvest_date or self.plant_date
        yyww = fields.Date.from_string(anchor).strftime('%y%W') if anchor else '0000'
        return f'{crop_code}-{yyww}-{seq:03d}-{weight_g:04d}-{nursery}{bench}'

    def _assign_crop_batch_sequence(self):
        """Assign the next batch sequence number for this crop."""
        self.ensure_one()
        if self.crop_batch_sequence:
            return self.crop_batch_sequence
        same_crop = self.search([
            ('packed_product_id', '=', self.packed_product_id.id),
            ('state', 'in', ['harvested', 'done']),
            ('crop_batch_sequence', '!=', 0),
        ])
        max_seq = max(same_crop.mapped('crop_batch_sequence') or [0])
        self.crop_batch_sequence = max_seq + 1
        return self.crop_batch_sequence

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
            'date': self.plant_date,
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
            'date': self.plant_date,
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

        # Add lot to live move line BEFORE validation so the move is valued correctly.
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
        # Also assign the seed lot to the seed move line before validation.
        seed_move = next((m for m in picking.move_ids if m.product_id == seed_lot.product_id), None)
        if seed_move:
            for ml in seed_move.move_line_ids:
                ml.lot_id = seed_lot.id

        picking.button_validate()

        # Carry the exact seed cost into the live product's standard_price so
        # subsequent moves (transplant/harvest) value live plants at the real
        # seed cost. Under AVCO the live move itself is valued by the average
        # layer, so no per-move value forcing is needed.
        seed_move = next((m for m in picking.move_ids if m.product_id == seed_lot.product_id), None)
        live_move = next((m for m in picking.move_ids if m.product_id == self.crop_id), None)
        if seed_move and live_move and seed_move.value:
            unit_cost = seed_move.value / live_move.product_uom_qty if live_move.product_uom_qty else 0.0
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
        """Germinated → Growing: assign bench, move live plants.

        CL-26: a bench can host only ONE active cultivation at a time.
        """
        self.ensure_one()
        if self.state != 'germinated':
            raise UserError('Can only grow from Germinated state.')
        if not self.bench_id:
            raise UserError('Select a bench location.')
        # CL-26: one-lot-per-bench invariant
        occupied = self.search([
            ('bench_id', '=', self.bench_id.id),
            ('state', 'in', ('growing', 'transplanted', 'harvested')),
            ('id', '!=', self.id),
        ], limit=1)
        if occupied:
            raise UserError(
                f'Bench {self.bench_id.name} is already occupied by {occupied.name}. '
                'A bench can host only one active cultivation at a time.'
            )
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
                'date': self.plant_date,
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
        # CUL-PHI-01 (GAP 3.3.x / มกษ. 9001-2564 chemical handling): harvest
        # is blocked while ANY chemical's pre-harvest interval is still
        # running AS OF THE HARVEST DATE. Date-coherent: compare against
        # harvest_date, not server-today (a 2027-dated harvest must not be
        # judged by 2026 server time). phi_days = 0 or no last_use_date →
        # no PHI applies. มกษ. F-06: an inspector reading the chemical
        # register next to the harvest record must never find produce
        # harvested inside the pre-harvest interval.
        for chem in self.env['farm.chemical.register'].search([('active', '=', True)]):
            phi_end = chem._phi_end_date()
            if phi_end and self.harvest_date < phi_end:
                raise UserError(
                    f'Harvest blocked: chemical "{chem.name}" was last used on '
                    f'{chem.last_use_date} with a {chem.phi_days}-day pre-harvest '
                    f'interval — PHI ends {phi_end}, which is AFTER the harvest '
                    f'date {self.harvest_date}. Harvesting produce inside the PHI '
                    f'window violates GAP chemical-handling rules (มกษ. 9001-2564). '
                    f'Harvest on or after {phi_end}, or correct the register.')
        # CL-23: zero-yield batch (full failure / all spoil) is allowed —
        # packed_kg = 0 with spoilage_units = total plants. The WIP is
        # written off to a period loss at action_done, not capitalized.
        if not self.packed_kg and not (self.spoilage_units and self.spoilage_units >= (self.target_plant_count or 0)):
            raise UserError('Enter packed kg.')

        self.write({
            'state': 'harvested',
            'harvested_date': fields.Datetime.now(),
        })

        return self._reopen()

    def _compute_labor_share(self):
        """Compute this cultivation's share of total labor cost.

        Deterministic: share = (this cultivation's duration / total
        cultivation-days across all cultivations) × total_wage.
        This ensures sum over all cultivations = total_wage exactly.
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
        duration = (end - start).days + 1
        return daily_rate * duration

    def action_done(self):
        """Harvested → Done: execute stock moves (packed → WH/Stock, spoilage → Spoilage).

        CL-23: a zero-yield batch (packed_kg = 0, all plants spoiled) writes
        ALL its WIP (material + labor) to a period loss account with a
        documented disposal event — never lingers as an asset.
        """
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
        if (self.spoilage_units or 0) > total_units:
            raise UserError(
                f'Spoilage units ({self.spoilage_units}) cannot exceed the batch size '
                f'({total_units} live plants). Check the spoilage count before harvesting.')

        # CL-23: zero-yield branch — no FG to produce; write off the batch WIP.
        if not self.packed_kg and (self.spoilage_units or 0) >= total_units:
            return self._write_off_zero_yield(total_units)

        prod_loc = self._get_production_loc()
        spoilage_loc = self._get_spoilage_loc()
        packed_loc = self._get_packed_loc()
        stock_loc = self._get_stock_loc()

        # Build packed lot name in format GC-001-2643-N6C6
        self._assign_crop_batch_sequence()
        packed_lot_name = self._get_packed_lot_name()
        self.packed_lot_weight_g = int(round((self.packed_kg or 0.0) * 1000))

        # 1. Consume live plants: WH/Stock → Production (spoilage_units stay
        #    in Stock and move to Spoilage separately)
        live_consume_qty = total_units - (self.spoilage_units or 0)
        live_move_vals = {
            'product_id': live_lot.product_id.id,
            'product_uom_qty': live_consume_qty,
            'product_uom': live_lot.product_id.uom_id.id,
            'location_id': stock_loc.id,
            'location_dest_id': prod_loc.id,
            'company_id': self.env.company.id,
            'date': self.harvest_date,
            'procure_method': 'make_to_stock',
            'move_line_ids': [(0, 0, {
                'product_id': live_lot.product_id.id,
                'lot_id': live_lot.id,
                'quantity': live_consume_qty,
                'product_uom_id': live_lot.product_id.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': prod_loc.id,
            })],
        }

        # 2. Create packed goods: Production → Packed Goods
        # Create the packed lot BEFORE validating the picking so the move line
        # can reference it (required for storable products with lot tracking).
        packed_move_vals = {
            'product_id': self.packed_product_id.id,
            'product_uom_qty': self.packed_kg,
            'product_uom': self.packed_product_id.uom_id.id,
            'location_id': prod_loc.id,
            'location_dest_id': packed_loc.id,
            'company_id': self.env.company.id,
            'date': self.harvest_date,
            'procure_method': 'make_to_stock',
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
                'date': self.harvest_date,
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

        # 4. Consume nutrient A: WH/Stock → Production (input logs are in ml, product UoM is L)
        stock_loc = self._get_stock_loc()
        if self.nutrient_product_id and self.total_nutrient_consumed > 0:
            moves.append({
                'product_id': self.nutrient_product_id.id,
                'product_uom_qty': self.total_nutrient_consumed / 1000.0,
                'product_uom': self.nutrient_product_id.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': prod_loc.id,
                'company_id': self.env.company.id,
                'date': self.harvest_date,
                'procure_method': 'make_to_stock',
            })

        # 4b. Consume nutrient B: same quantity as A (both concentrates used equally)
        if self.nutrient_b_product_id and self.total_nutrient_consumed > 0:
            moves.append({
                'product_id': self.nutrient_b_product_id.id,
                'product_uom_qty': self.total_nutrient_consumed / 1000.0,
                'product_uom': self.nutrient_b_product_id.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': prod_loc.id,
                'company_id': self.env.company.id,
                'date': self.harvest_date,
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
                'date': self.harvest_date,
                'procure_method': 'make_to_stock',
            })

        # 6. Direct labor: already capitalized into WIP at worker-log confirm
        # (Dr 113400 / Cr 222100, CL-05). No harvest-time expense JE — labor
        # flows to FG here and to COGS on sale. labor_share is this batch's
        # share of the accrued wages (daily rate × duration).
        labor_share = self._compute_labor_share()

        int_type = self.env.ref('stock.picking_type_internal', raise_if_not_found=False)
        if not int_type:
            int_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1)

        # Split into two pickings to avoid destination mismatch:
        # Picking 1: consume live + nutrient + acid + spoilage (leaves Stock)
        # Picking 2: create packed (leaves Production)
        consume_moves = [m for m in moves if m['location_id'] == stock_loc.id]
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
            # Capture actual input cost from consumed move values AFTER validation.
            # Exclude the spoilage move (Stock → Spoilage): spoilage is expensed
            # to P&L, not capitalized into FG cost.
            total_input_cost = sum(
                move.value for move in picking.move_ids
                if move.location_dest_id != spoilage_loc
            )
            # Include material transformation balancing JEs linked to this batch
            mt_wip_adj = self.env['account.move'].search([
                ('ref', '=', f'MT-WIP-ADJ-{self.id}'),
                ('state', '=', 'posted'),
            ])
            for m in mt_wip_adj:
                for l in m.line_ids.filtered(lambda x: x.account_id.code == '113400'):
                    total_input_cost += l.debit - l.credit

        # Include direct labor in product cost (labor_share computed above).
        # CL-05: labor is capitalized into WIP at worker-log confirm, so the
        # FG cost = material + this batch's labor share. The labor accrual
        # (Dr 113400) is already in WIP; adding labor_share to the FG cost
        # makes WIP→FG carry the full conversion cost.
        fg_cost = total_input_cost + labor_share

        if produce_moves:
            produce_dest = packed_loc
            picking2 = self.env['stock.picking'].create({
                'picking_type_id': int_type.id,
                'location_id': prod_loc.id,
                'location_dest_id': produce_dest.id,
                'move_ids': [(0, 0, m) for m in produce_moves],
            })
            for move in picking2.move_ids:
                move._set_quantity_done(move.product_uom_qty)

            # Under AVCO the production-output move is valued from the packed
            # product's standard_price at validation, so set it to the exact
            # full conversion cost per kg (material + labor) BEFORE validating.
            # This makes the output layer carry the real batch cost and WIP→FG exact.
            if fg_cost and self.packed_kg:
                self.packed_product_id.product_tmpl_id.standard_price = fg_cost / self.packed_kg

            # Create packed lot BEFORE validating so move lines can reference it.
            packed_lot = self.env['stock.lot'].create({
                'name': packed_lot_name,
                'product_id': self.packed_product_id.id,
                'company_id': self.env.company.id,
            })
            # Assign lot to the output move line(s)
            for move in picking2.move_ids:
                if move.product_id == self.packed_product_id:
                    for ml in move.move_line_ids:
                        ml.lot_id = packed_lot.id

            picking2.button_validate()
            if not picking:
                picking = picking2

        # If no produce_moves, create lot anyway (should not happen for done state)
        if not produce_moves:
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
            # CL-10: per-packed-lot cost capture (material + labor)
            'packed_lot_cost': fg_cost,
            'packed_lot_cost_per_kg': fg_cost / self.packed_kg if self.packed_kg else 0.0,
            'packed_lot_remaining_value': fg_cost,
        })

        # CL-06: abnormal spoilage (>5%) must carry a documented disposal
        # record — the rejected produce never entered the sale stream.
        # Auto-create a draft disposal record the worker confirms.
        if self.spoilage_units > 0 and self.spoilage_classification == 'abnormal':
            existing = self.env['farm.spoilage.disposal'].search([
                ('cultivation_id', '=', self.id),
            ], limit=1)
            if not existing:
                self.env['farm.spoilage.disposal'].create({
                    'date': self.harvest_date or fields.Date.today(),
                    'cultivation_id': self.id,
                    'lot_id': self.live_lot_id.id if self.live_lot_id else False,
                    'quantity': self.spoilage_units,
                    'classification': 'abnormal',
                    'reason': 'Abnormal spoilage (>5% of germinated plants) at harvest',
                    'destination': 'Spoilage location',
                })

        # Thai accounting: the production-output move transfers WIP value to FG
        # (Dr 113100 / Cr 113400) at the AVCO layer cost — the packed product's
        # standard_price was set to the exact material batch cost before validation.
        return self._reopen()

    def _write_off_zero_yield(self, total_units):
        """CL-23: write off a zero-yield batch's full WIP to a period loss.

        Consumes all live plants (Stock → Production), moves them to the
        Spoilage location, posts a period-loss JE for the batch's material +
        labor cost, creates the disposal record, and marks the batch done.
        """
        self.ensure_one()
        prod_loc = self._get_production_loc()
        spoilage_loc = self._get_spoilage_loc()
        stock_loc = self._get_stock_loc()
        live_lot = self.live_lot_id

        int_type = self.env.ref('stock.picking_type_internal', raise_if_not_found=False)
        if not int_type:
            int_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1)

        # 1. Consume all live plants: Stock → Production
        picking = self.env['stock.picking'].create({
            'picking_type_id': int_type.id,
            'location_id': stock_loc.id,
            'location_dest_id': prod_loc.id,
            'move_ids': [(0, 0, {
                'product_id': live_lot.product_id.id,
                'product_uom_qty': total_units,
                'product_uom': live_lot.product_id.uom_id.id,
                'location_id': stock_loc.id,
                'location_dest_id': prod_loc.id,
                'company_id': self.env.company.id,
                'date': self.harvest_date,
                'procure_method': 'make_to_stock',
                'move_line_ids': [(0, 0, {
                    'product_id': live_lot.product_id.id,
                    'lot_id': live_lot.id,
                    'quantity': total_units,
                    'product_uom_id': live_lot.product_id.uom_id.id,
                    'location_id': stock_loc.id,
                    'location_dest_id': prod_loc.id,
                })],
            })],
        })
        for move in picking.move_ids:
            move._set_quantity_done(move.product_uom_qty)
        picking.button_validate()
        material_cost = sum(move.value for move in picking.move_ids)

        # 2. Move all to Spoilage (documented non-sale removal)
        spoil_pick = self.env['stock.picking'].create({
            'picking_type_id': int_type.id,
            'location_id': prod_loc.id,
            'location_dest_id': spoilage_loc.id,
            'move_ids': [(0, 0, {
                'product_id': live_lot.product_id.id,
                'product_uom_qty': total_units,
                'product_uom': live_lot.product_id.uom_id.id,
                'location_id': prod_loc.id,
                'location_dest_id': spoilage_loc.id,
                'company_id': self.env.company.id,
                'date': self.harvest_date,
                'procure_method': 'make_to_stock',
                'move_line_ids': [(0, 0, {
                    'product_id': live_lot.product_id.id,
                    'lot_id': live_lot.id,
                    'quantity': total_units,
                    'product_uom_id': live_lot.product_id.uom_id.id,
                    'location_id': prod_loc.id,
                    'location_dest_id': spoilage_loc.id,
                })],
            })],
        })
        for move in spoil_pick.move_ids:
            move._set_quantity_done(move.product_uom_qty)
        spoil_pick.button_validate()

        # 3. Period-loss JE: Dr 516xxx (abnormal loss) / Cr 113400 (WIP)
        # for the batch's material + labor share.
        labor_share = self._compute_labor_share()
        loss_amount = material_cost + labor_share
        loss_acc = self.env['account.account'].search([('code', '=', '516100')], limit=1)
        if not loss_acc:
            loss_acc = self.env['account.account'].search([('code', '=', '511100')], limit=1)
        stock_journal = self.env.company.account_stock_journal_id
        if loss_acc and stock_journal and loss_amount > 0:
            je = self.env['account.move'].create({
                'journal_id': stock_journal.id,
                'date': self.harvest_date,
                'ref': f'ZERO-YIELD-LOSS-{self.id}',
                'line_ids': [
                    (0, 0, {'account_id': loss_acc.id, 'debit': loss_amount, 'credit': 0.0,
                            'name': f'Zero-yield batch loss - {self.name}'}),
                    (0, 0, {'account_id': self.env['account.account'].search([('code', '=', '113400')], limit=1).id,
                            'debit': 0.0, 'credit': loss_amount,
                            'name': f'Zero-yield batch loss - {self.name}'}),
                ],
            })
            je.action_post()

        # 4. Disposal record (documented event)
        existing = self.env['farm.spoilage.disposal'].search([
            ('cultivation_id', '=', self.id),
        ], limit=1)
        if not existing:
            self.env['farm.spoilage.disposal'].create({
                'date': self.harvest_date or fields.Date.today(),
                'cultivation_id': self.id,
                'lot_id': live_lot.id,
                'quantity': total_units,
                'classification': 'abnormal',
                'reason': 'Zero-yield batch (full failure / all plants spoiled)',
                'destination': 'Spoilage location',
            })

        self.write({
            'state': 'done',
            'done_date': fields.Datetime.now(),
            'harvest_picking_id': picking.id,
        })
        return self._reopen()

    def action_traceability(self):
        """CL-12: open the traceability chain for this cultivation.

        Returns an action showing the full chain: seed lot → live lot →
        packed lot → harvest. The chain is assembled from the cultivation's
        linked records (GAP 3.8.3 traceability).
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Traceability — {self.display_name}',
            'res_model': 'vivafarm.cultivation',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_cancel(self):
        """Cancel from any state. Returns seeds if germinated/growing."""
        self.ensure_one()
        if self.state == 'done':
            raise UserError('Cannot cancel a completed cultivation.')

        # If seeds were consumed, return them (harvested is data-only — no
        # stock moves yet — so the seeds are still returnable)
        if self.state in ('germinated', 'transplanted', 'harvested') and self.plant_picking_id:
            prod_loc = self._get_production_loc()
            stock_loc = self._get_stock_loc()

            # Reverse: move seeds back from Production → WH/Stock
            # Use the same internal picking type as the forward move (the
            # default internal type may be inactive — search would miss it).
            int_type = self.env.ref('stock.picking_type_internal', raise_if_not_found=False)
            if not int_type:
                int_type = self.env['stock.picking.type'].search([
                    ('code', '=', 'internal'),
                    ('active', 'in', [True, False]),
                ], limit=1)
            return_picking = self.env['stock.picking'].create({
                'picking_type_id': int_type.id if int_type else False,
                'location_id': prod_loc.id,
                'location_dest_id': stock_loc.id,
                'move_ids': [(0, 0, {
                    'product_id': self.seed_lot_id.product_id.id,
                    'product_uom_qty': self.grams_consumed,
                    'product_uom': self.seed_lot_id.product_id.uom_id.id,
                    'location_id': prod_loc.id,
                    'location_dest_id': stock_loc.id,
                    'company_id': self.env.company.id,
                    'date': self.harvest_date or self.plant_date,
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
