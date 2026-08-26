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
    nutrient_b_product_id = fields.Many2one(
        'product.product', string='Nutrient B Product',
        domain="[('type', '=', 'consu')]",
        help='Second nutrient concentrate consumed in equal quantity')
    acid_product_id = fields.Many2one(
        'product.product', string='Acid Product',
        domain="[('type', '=', 'consu')]",
        help='Acid product consumed during this cycle')

    # Default quantities
    grams_to_sow = fields.Float(string='Grams to Sow', default=0.5, required=True)
    target_plant_count = fields.Integer(string='Target Plants', default=240, required=True)
    transplant_amount = fields.Integer(string='Transplant Amount', default=240, required=True)

    # CL-27: F-04 target bands (GAP 3.5.1 — the acceptable EC/pH range)
    target_ec_min = fields.Float(string='Target EC Min', default=1.2, digits=(4, 2))
    target_ec_max = fields.Float(string='Target EC Max', default=2.0, digits=(4, 2))
    target_ph_min = fields.Float(string='Target pH Min', default=5.5, digits=(3, 1))
    target_ph_max = fields.Float(string='Target pH Max', default=6.5, digits=(3, 1))

    # Durations (ideal days)
    germinate_duration = fields.Integer(
        string='Germinate Duration (days)', default=7,
        help='Ideal days in Germinate phase. Used to calculate target transplant date.')
    total_grow_duration = fields.Integer(
        string='Total Grow Duration (days)', default=28,
        help='Ideal total days from plant date to harvest. Used to calculate target harvest date.')

    # Default nursery
    nursery_id = fields.Many2one(
        'farm.location', string='Default Nursery',
        domain="[('location_type', '=', 'nursery')]",
        help='Default nursery location for this recipe')

    notes = fields.Text(string='Notes')
