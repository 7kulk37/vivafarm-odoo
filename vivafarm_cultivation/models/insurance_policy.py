from odoo import fields, models, api
from odoo.exceptions import UserError


class FarmInsurancePolicy(models.Model):
    _name = 'farm.insurance.policy'
    _description = 'Insurance Policy (CL-35)'
    _order = 'coverage_end asc, id'
    _rec_name = 'policy_number'

    policy_number = fields.Char(
        string='Policy Number',
        required=True,
    )
    insurer = fields.Char(
        string='Insurer',
        required=True,
    )
    coverage_type = fields.Selection([
        ('crop', 'Crop'),
        ('equipment', 'Equipment'),
        ('liability', 'Liability'),
        ('other', 'Other'),
    ], string='Coverage Type', default='crop', required=True)
    coverage_start = fields.Date(
        string='Coverage Start',
        required=True,
    )
    coverage_end = fields.Date(
        string='Coverage End',
        required=True,
    )
    premium = fields.Monetary(
        string='Premium (THB)',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    premises = fields.Char(
        string='Premises',
        help='Site/asset covered',
    )
    is_active = fields.Boolean(
        string='Active',
        compute='_compute_active',
        store=True,
        help='True while today is within the coverage window',
    )
    days_to_expiry = fields.Integer(
        string='Days to Expiry',
        compute='_compute_active',
        store=True,
        help='Days until coverage ends (0 if expired) — renewal reminder',
    )
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    @api.depends('coverage_start', 'coverage_end')
    def _compute_active(self):
        today = fields.Date.today()
        for record in self:
            if record.coverage_start and record.coverage_end:
                record.is_active = record.coverage_start <= today <= record.coverage_end
                if record.is_active:
                    record.days_to_expiry = (record.coverage_end - today).days
                else:
                    record.days_to_expiry = 0
            else:
                record.is_active = False
                record.days_to_expiry = 0
