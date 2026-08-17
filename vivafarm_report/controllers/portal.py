"""Portal route for the Viva Quotation/Sale Order PDF.

Standard portal "View Details" (sale.controllers.portal.portal_order_page,
report_ref='sale.action_report_saleorder') renders the DEFAULT Odoo report.
The user asked for a NEW button — "View Quotation / Sale Order" — that renders
the custom Viva report (vivafarm_report.viva_quotation_so) instead. This route
never touches the standard one.
"""
from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.sale.controllers.portal import CustomerPortal


class VivaSalePortal(CustomerPortal):

    @http.route(['/my/orders/<int:order_id>/viva_pdf'], type='http',
                auth="public", website=True)
    def portal_order_viva_pdf(self, order_id, access_token=None, download=False, **kw):
        try:
            order_sudo = self._document_check_access(
                'sale.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        # env-level render so vivafarm_document_sign's override serves the
        # stored signed PDF when the order was accepted on the portal.
        report = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'vivafarm_report.viva_quotation_so', [order_sudo.id])[0]
        headers = self._get_http_headers(order_sudo, 'pdf', report, download)
        return request.make_response(report, headers=list(headers.items()))
