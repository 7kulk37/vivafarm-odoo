from odoo import fields, models


class FarmLocation(models.Model):
    _name = 'farm.location'
    _description = 'Farm Location - Simple location registry'
    _order = 'name asc'

    name = fields.Char(string='Name', required=True)
    location_type = fields.Selection([
        ('nursery', 'Nursery'),
        ('bench', 'Bench'),
        ('buffer', 'Buffer'),
        ('packed', 'Packed Goods'),
        ('spoilage', 'Spoilage'),
        ('other', 'Other'),
    ], string='Type', required=True, default='bench')
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')
