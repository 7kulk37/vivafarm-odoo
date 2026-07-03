from odoo import fields, models, api


class Recipe(models.Model):
    _name = 'vivafarm.recipe'
    _description = 'Cultivation recipe - template of defaults for one crop type'
    _order = 'name asc'
    _rec_name = 'name'

    name = fields.Char(string='Recipe Name', required=True)
    active = fields.Boolean(string='Active', default=True)

    # Products
    seed_product_id = fields.Many2one(
        'product.product', string='Seed Product', required=True,
        domain="[('name', 'ilike', 'Seeds')]",
        help='Seed product used for this crop')
    crop_id = fields.Many2one(
        'product.product', string='Crop', required=True,
        domain="[('name', 'ilike', '(Live)')]",
        help='Live crop product')
    packed_product_id = fields.Many2one(
        'product.product', string='Packed Product', required=True,
        domain="[('name', 'ilike', '(Packed)')]",
        help='Packed product produced at harvest')
    nutrient_product_id = fields.Many2one(
        'product.product', string='Nutrient Product',
        domain="[('type', '=', 'consu')]",
        help='Nutrient product consumed during this cycle')
    acid_product_id = fields.Many2one(
        'product.product', string='Acid Product',
        domain="[('type', '=', 'consu')]",
        help='Acid product consumed during this cycle')

    # Default quantities
    grams_to_sow = fields.Float(string='Grams to Sow', default=0.5, required=True)
    target_plant_count = fields.Integer(string='Target Plants', default=240, required=True)
    transplant_amount = fields.Integer(string='Transplant Amount', default=240, required=True)

    # Durations (ideal days)
    germinate_duration = fields.Integer(
        string='Germinate Duration (days)', default=7,
        help='Ideal days in Germinate phase. Used to calculate target transplant date.')
    total_grow_duration = fields.Integer(
        string='Total Grow Duration (days)', default=28,
        help='Ideal total days from plant date to harvest. Used to calculate target harvest date.')

    # Default nursery
    nursery_id = fields.Many2one(
        'stock.location', string='Default Nursery',
        domain="[('usage', '=', 'internal'), ('name', 'ilike', 'Nursery')]",
        help='Default nursery location for this recipe')

    notes = fields.Text(string='Notes')
