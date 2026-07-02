from odoo import fields, models, api


class StockLot(models.Model):
    _inherit = 'stock.lot'

    x_seed_lot = fields.Char(
        string='Seed Lot',
        help='Seed lot number from supplier (e.g. GO-2026-04)',
    )

    @api.model
    def create(self, vals_list):
        """Auto-generate lot name for seed products."""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if vals.get('product_id') and not vals.get('name'):
                product = self.env['product.product'].browse(vals['product_id'])
                prefix = self._get_seed_prefix(product.name)
                if prefix:
                    vals['name'] = self._next_seed_lot(prefix)
        return super().create(vals_list)

    @api.model
    def _get_seed_prefix(self, product_name):
        """Map product name to seed lot prefix."""
        mapping = {
            'green oak': 'GO',
            'red oak': 'RO',
            'green cos': 'GC',
        }
        name_lower = product_name.lower()
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

        # Clamp at 0xFFF (4095)
        if next_val > 0xFFF:
            next_val = 1

        Param.set_param(key, format(next_val, 'X'))
        return f'{prefix}-{format(next_val, "03X")}'


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _get_seed_lot_name(self, product_id):
        """Auto-generate lot name for seed products on move lines."""
        product = self.env['product.product'].browse(product_id)
        prefix = self.env['stock.lot']._get_seed_prefix(product.name)
        if prefix:
            return self.env['stock.lot']._next_seed_lot(prefix)
        return False

    @api.model
    def create(self, vals_list):
        """Auto-fill lot_name for seed products during receipt."""
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if vals.get('product_id') and not vals.get('lot_name'):
                lot_name = self._get_seed_lot_name(vals['product_id'])
                if lot_name:
                    vals['lot_name'] = lot_name
        return super().create(vals_list)
