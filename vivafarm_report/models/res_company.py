from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_th_signature_image = fields.Binary(
        string='Signature Image (ลายมือชื่อผู้มีอำนาจลงนาม)',
        help='Upload an image of the authorized person\'s signature for display on Thai Tax Invoices.',
    )
    l10n_th_branch_name = fields.Char(
        string='Branch Name (สาขา)',
        help='Branch name for Thai Tax Invoice. Leave empty if head office.',
    )
    l10n_th_branch_number = fields.Char(
        string='Branch Number',
        help='Branch number (e.g., 00000 for head office).',
        default='00000',
    )
