"""ir.actions.report override — serve the stored signed PDF on print.

wkhtmltopdf embeds a /CreationDate in every render, so re-rendering a
signed invoice NEVER reproduces the bytes that were hashed + signed. To
keep "print == signed == verified", the report must return the STORED
signed PDF (the exact bytes from the signature) whenever a signed
document exists — never a fresh render.

Scoped strictly to the Viva tax invoice report; all other reports fall
through to the standard path.
"""
import base64

from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref) if report_ref else False
        if (
            report and report.report_name == 'vivafarm_report.viva_invoice'
            and isinstance(res_ids, (list, tuple)) and len(res_ids) == 1
        ):
            signed = self.env['viva.signed.document'].sudo().search([
                ('move_id', '=', res_ids[0]),
                ('state', 'in', ('signed', 'revoked')),
                ('signed_attachment_id', '!=', False),
            ], limit=1)
            if signed:
                return base64.b64decode(signed.signed_attachment_id.datas), 'pdf'
        if (
            report and report.report_name == 'vivafarm_report.viva_quotation_so'
            and isinstance(res_ids, (list, tuple)) and len(res_ids) == 1
        ):
            signed = self.env['viva.signed.document'].sudo().search([
                ('sale_order_id', '=', res_ids[0]),
                ('state', 'in', ('signed', 'revoked')),
                ('signed_attachment_id', '!=', False),
            ], limit=1)
            if signed:
                return base64.b64decode(signed.signed_attachment_id.datas), 'pdf'
        if (
            report and report.report_name == 'vivafarm_report.viva_delivery_note'
            and isinstance(res_ids, (list, tuple)) and len(res_ids) == 1
        ):
            signed = self.env['viva.signed.document'].sudo().search([
                ('picking_id', '=', res_ids[0]),
                ('state', 'in', ('signed', 'revoked')),
                ('signed_attachment_id', '!=', False),
            ], limit=1)
            if signed:
                return base64.b64decode(signed.signed_attachment_id.datas), 'pdf'
        return super()._render_qweb_pdf(report_ref, res_ids, data)
