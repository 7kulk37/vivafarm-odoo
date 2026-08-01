from odoo import fields, models


class BaseDocumentLayout(models.TransientModel):
    _inherit = 'base.document.layout'

    l10n_th_branch_name = fields.Char(related='company_id.l10n_th_branch_name', readonly=True)
    l10n_th_branch_number = fields.Char(related='company_id.l10n_th_branch_number', readonly=True)
