from odoo import fields, models


class VivaPndReturn(models.Model):
    """PND 3/53 filing record (VS-07).

    One record per (form, tax period). The owner e-files on the RD portal
    and records the filing here: filed date + filing number + type
    (original / amended). The amended type covers the missed-WHT
    self-correction path (ยื่นเพิ่มเติม + §27 surcharge) — e.g. a
    construction service paid without withholding.
    """

    _name = 'viva.pnd.return'
    _description = 'Thai PND 3/53 Filing Record'
    _order = 'period_from desc'

    form_type = fields.Selection([
        ('pnd3', 'PND3 (ภ.ง.ด.3) — individuals'),
        ('pnd53', 'PND53 (ภ.ง.ด.53) — companies'),
    ], string='Form', required=True)
    period_from = fields.Date(string='Period From', required=True)
    period_to = fields.Date(string='Period To', required=True)
    return_type = fields.Selection([
        ('original', 'Original (ปกติ)'),
        ('amended', 'Amended / Additional (เพิ่มเติม)'),
    ], string='Type', required=True, default='original')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('filed', 'Filed'),
    ], string='State', default='draft')
    filed_date = fields.Date(string='Filed Date')
    filing_number = fields.Char(string='Filing Number')
    surcharge = fields.Float(
        string='Surcharge (เงินเพิ่ม)',
        help='§27 1.5%/month surcharge on late/amended remittance. '
             'Recorded as a note — never booked as a tax.',
    )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )
    note = fields.Text(string='Note')

    def action_mark_filed(self):
        self.ensure_one()
        self.write({'state': 'filed', 'filed_date': fields.Date.context_today(self)})
        return True
