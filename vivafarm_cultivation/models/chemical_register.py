from odoo import fields, models, api
from odoo.exceptions import UserError
from datetime import timedelta


class FarmChemicalRegister(models.Model):
    _name = 'farm.chemical.register'
    _description = 'Chemical Register (F-06)'
    _order = 'name asc'
    _rec_name = 'name'

    name = fields.Char(
        string='Chemical Name',
        required=True,
        help='Trade name of the chemical',
    )
    active_ingredient = fields.Char(
        string='Active Ingredient',
        help='Active ingredient (e.g. nitric acid 68%)',
    )
    phi_days = fields.Integer(
        string='PHI (days)',
        default=0,
        help='Pre-harvest interval in days — harvest is blocked until this elapses',
    )
    sds_on_file = fields.Boolean(
        string='SDS on File',
        help='Safety Data Sheet filed (HSA 2535 / GAP 3.7.7)',
    )
    last_use_date = fields.Date(
        string='Last Use Date',
        help='Last date the chemical was used on the farm',
    )
    phi_elapsed = fields.Boolean(
        string='PHI Elapsed',
        compute='_compute_phi_elapsed',
        store=True,
        help='True when the pre-harvest interval has elapsed since last use',
    )
    notes = fields.Text(string='Notes')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    ref = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        help='Auto-generated reference number',
    )

    @api.depends('last_use_date', 'phi_days')
    def _compute_phi_elapsed(self):
        """CL-17: PHI elapsed when last_use_date + phi_days <= today."""
        today = fields.Date.today()
        for record in self:
            if not record.last_use_date or not record.phi_days:
                record.phi_elapsed = True
                continue
            record.phi_elapsed = (record.last_use_date + timedelta(days=record.phi_days)) <= today

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if not vals.get('ref'):
                vals['ref'] = self.env['ir.sequence'].next_by_code('farm.chemical.register') or '/'
        return super(FarmChemicalRegister, self).create(vals_list)

    def action_use(self):
        """Record a chemical use (sets last_use_date to today)."""
        for record in self:
            record.last_use_date = fields.Date.today()
        return True
