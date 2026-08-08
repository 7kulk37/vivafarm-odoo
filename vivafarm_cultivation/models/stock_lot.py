from odoo import fields, models, api


class StockLot(models.Model):
    _inherit = 'stock.lot'

    x_seed_lot = fields.Char(
        string='Seed Lot',
        help='Seed lot number from supplier (e.g. GO-2026-04)',
    )

    @api.depends('name')
    def _compute_display_complete(self):
        """Always show quantity and location fields on lot form."""
        for lot in self:
            lot.display_complete = True

    @api.onchange('product_id')
    def _onchange_product_id_lot(self):
        """When product changes on form: auto-generate name for seeds, clear for others."""
        if not self.product_id:
            return
        if self._is_seed_product(self.product_id.name):
            prefix = self._get_seed_prefix(self.product_id.name)
            if prefix:
                self.name = self._next_seed_lot(prefix)
        else:
            self.name = False
        self.display_complete = True

    @api.model
    def create(self, vals_list):
        """Auto-generate lot name for seed products only.

        For seed products:
        - Always generate the hex code (e.g. GO-00A) into x_seed_lot.
        - If no manual name was given, the hex code becomes the lot name.
        - If a manual name was given (e.g. GO-2632-00A-SDJKASD), keep it.
        """
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                if self._is_seed_product(product.name):
                    prefix = self._get_seed_prefix(product.name)
                    if prefix:
                        hex_code = self._next_seed_lot(prefix)
                        vals['x_seed_lot'] = hex_code
                        if not vals.get('name'):
                            vals['name'] = hex_code
        return super().create(vals_list)

    @api.model
    def _is_seed_product(self, product_name):
        """Check if product name indicates a seed product.

        Real product names are 'Seeds (packed 0.5 g) - Green Oak' etc.
        Live/Packed products ('Green Oak (Live)') must NOT match.
        """
        name_lower = product_name.lower() if product_name else ''
        return name_lower.startswith('seeds')

    @api.model
    def _get_seed_prefix(self, product_name):
        """Map product name to seed lot prefix."""
        mapping = {
            'green oak': 'GO',
            'red oak': 'RO',
            'green cos': 'GC',
        }
        name_lower = product_name.lower() if product_name else ''
        for key, prefix in mapping.items():
            if key in name_lower:
                return prefix
        return False

    @api.model
    def _next_seed_lot(self, prefix):
        """Get next hex lot number for a prefix, stored in ir.config_parameter."""
        key = f'vivafarm.seed_seq.{prefix}'
        Param = self.env['ir.config_parameter']

        current = Param.get_param(key, default='0')
        try:
            next_val = int(current, 16) + 1
        except ValueError:
            next_val = 1

        if next_val > 0xFFF:
            next_val = 1

        Param.set_param(key, format(next_val, 'X'))
        return f'{prefix}-{format(next_val, "03X")}'

    @api.model
    def _peek_seed_hex(self, prefix):
        """Peek the next hex code WITHOUT consuming the sequence.

        Used for the receipt placeholder — rendering the hint must not
        burn a lot number. The sequence only advances on actual lot create.
        """
        key = f'vivafarm.seed_seq.{prefix}'
        Param = self.env['ir.config_parameter']
        current = Param.get_param(key, default='0')
        try:
            next_val = int(current, 16) + 1
        except ValueError:
            next_val = 1
        if next_val > 0xFFF:
            next_val = 1
        return f'{prefix}-{format(next_val, "03X")}'

    @api.model
    def _get_seed_lot_placeholder(self, product_id):
        """Calculated grey placeholder for the receipt Lot/Serial field.

        Format: eg. GO-2632-00A-EXTERNAL
        - GO   = suggested seed type (prefix from product name)
        - 2632 = suggested year + ISO week of purchase (today)
        - 00A  = suggested hex internal code (peeked, not consumed)
        - EXTERNAL = literal word — the receiver types the supplier ref over it
        Returns False for non-seed products (fall back to stock default).
        """
        product = self.env['product.product'].browse(product_id)
        if not product or not self._is_seed_product(product.name):
            return False
        prefix = self._get_seed_prefix(product.name)
        if not prefix:
            return False
        from datetime import date
        today = date.today()
        year_week = f'{today.year % 100}{today.isocalendar()[1]:02d}'
        hex_code = self._peek_seed_hex(prefix)
        return f'eg. {prefix}-{year_week}-{hex_code.split("-", 1)[1]}-EXTERNAL'

    def _check_unique_lot(self):
        """Override: skip uniqueness check for live crop products (allow duplicate YY-WW lots)."""
        live_products = self.filtered(lambda l: l.product_id and 'live' in l.product_id.name.lower())
        if live_products:
            # Skip validation for live crop products — duplicates allowed
            other = self - live_products
            if other:
                super(StockLot, other)._check_unique_lot()
            return
        return super()._check_unique_lot()


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    lot_name_placeholder = fields.Char(
        string='Lot Placeholder',
        compute='_compute_lot_name_placeholder',
        help='Calculated grey placeholder for the Lot/Serial Number field on receipts.',
    )

    @api.depends('product_id')
    def _compute_lot_name_placeholder(self):
        """Per-product grey placeholder for the receipt Lot/Serial field.

        Seeds: 'eg. GO-2632-00A-EXTERNAL' (calculated, sequence peeked not consumed).
        Others: stock default 'e.g. SN000001'.
        """
        for line in self:
            if line.product_id:
                ph = self.env['stock.lot']._get_seed_lot_placeholder(line.product_id.id)
                if ph:
                    line.lot_name_placeholder = ph
                    continue
            line.lot_name_placeholder = 'e.g. SN000001'

    def _get_seed_lot_name(self, product_id):
        """Hex-format generator for seed lots (GO-00A).

        Kept active per user decision — the hex code feeds x_seed_lot on
        lot create (see StockLot.create). The receipt itself is MANUAL
        entry: the receiver types the full lot number over the placeholder.
        """
        product = self.env['product.product'].browse(product_id)
        if not self.env['stock.lot']._is_seed_product(product.name):
            return False
        prefix = self.env['stock.lot']._get_seed_prefix(product.name)
        if prefix:
            return self.env['stock.lot']._next_seed_lot(prefix)
        return False