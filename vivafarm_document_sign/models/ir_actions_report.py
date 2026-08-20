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
                # The portal-acknowledged plain Invoice (ใบแจ้งหนี้) ALSO
                # carries move_id — without this filter, the TAX invoice
                # report would serve the plain-invoice signed bytes (and
                # the reverse). Each report serves only its own type.
                ('document_type', '=', 'tax_invoice'),
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
                # The delivery_note signed record ALSO carries sale_order_id
                # as the chain link — without this filter, "View Quotation /
                # Sale Order" would serve the signed Delivery Confirmation
                # PDF instead of the signed Sale Order (user report
                # 2026-08-19).
                ('document_type', '=', 'sale_order'),
                ('state', 'in', ('signed', 'revoked')),
                ('signed_attachment_id', '!=', False),
            ], limit=1)
            if signed:
                return base64.b64decode(signed.signed_attachment_id.datas), 'pdf'
        if (
            report and report.report_name == 'vivafarm_report.viva_invoice_plain'
            and isinstance(res_ids, (list, tuple)) and len(res_ids) == 1
        ):
            signed = self.env['viva.signed.document'].sudo().search([
                ('move_id', '=', res_ids[0]),
                ('document_type', '=', 'invoice'),
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
