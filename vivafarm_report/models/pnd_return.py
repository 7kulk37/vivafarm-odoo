from odoo import api, fields, models


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
    # VS-19: filed-on-time marker — computed from filed_date vs the 15th
    # e-filing deadline of the month after the period end. Surcharge stays
    # 0 unless the owner opts into real §27 computation.
    filed_on_time = fields.Boolean(
        string='Filed On Time',
        compute='_compute_filed_on_time',
        help='True when filed_date ≤ the 15th e-filing deadline of the '
             'month after the period end (VS-19).',
    )

    @api.depends('filed_date', 'period_to')
    def _compute_filed_on_time(self):
        for rec in self:
            if not rec.filed_date or not rec.period_to:
                rec.filed_on_time = False
                continue
            # E-filing deadline: the 15th of the month AFTER the period end.
            if rec.period_to.month == 12:
                deadline = rec.period_to.replace(year=rec.period_to.year + 1, month=1, day=15)
            else:
                deadline = rec.period_to.replace(month=rec.period_to.month + 1, day=15)
            rec.filed_on_time = rec.filed_date <= deadline
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )
    note = fields.Text(string='Note')

    def action_mark_filed(self):
        self.ensure_one()
        self.write({'state': 'filed', 'filed_date': fields.Date.context_today(self)})
        return True
