"""Portal routes for the Viva Quotation/Sale Order PDF and acceptance.

1. portal_order_viva_pdf — "View Quotation / Sale Order" button. Standard
   portal "View Details" (sale.controllers.portal.portal_order_page,
   report_ref='sale.action_report_saleorder') renders the DEFAULT Odoo
   report. The user asked for a NEW button rendering the custom Viva report
   (vivafarm_report.viva_quotation_so). This route never touches the
   standard one.

2. portal_order_accept_viva — "Accept & Sign quotation" button. The standard
   accept route (sale.controllers.portal.portal_quote_accept) sends the
   confirmation email via sale.mail_template_sale_confirmation (template 21)
   whose report is sale.report_saleorder — the DEFAULT form — and the email
   is sent INSIDE action_confirm BEFORE vivafarm_document_sign hashes the
   order. This route: (a) writes the customer signature, (b) confirms FIRST
   (action_confirm -> signature present -> hash + stored signed PDF created),
   (c) sends the VIVA confirmation template (vivafarm_report.
   viva_email_template_order_confirmation) whose report is
   vivafarm_report.viva_quotation_so — so ir_actions_report._render_qweb_pdf
   serves the STORED SIGNED bytes in the email, (d) posts the same signed
   PDF in the chatter.
"""
from odoo import fields, http
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

    @http.route(['/my/orders/<int:order_id>/accept_viva'], type='jsonrpc',
                auth="public", website=True)
    def portal_order_accept_viva(self, order_id, access_token=None, name=None,
                                 signature=None):
        # Same access + preconditions as the standard accept route.
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            order_sudo = self._document_check_access(
                'sale.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return {'error': 'Invalid order.'}

        if not order_sudo._has_to_be_signed():
            return {'error': 'The order is not in a state requiring customer signature.'}
        if not signature:
            return {'error': 'Signature is missing.'}

        try:
            order_sudo.write({
                'signed_by': name,
                'signed_on': fields.Datetime.now(),
                'signature': signature,
            })
            # flush now to make signature data available to PDF render request
            request.env.cr.flush()
        except (TypeError, Exception):
            return {'error': 'Invalid signature data.'}

        # (b) Confirm FIRST — the vivafarm_document_sign action_confirm
        # override sees signature + state sale and creates the signed
        # document + stored signed PDF.
        if not order_sudo._has_to_be_paid():
            order_sudo.with_context(sale_include_signature=True).action_confirm()

        # (c) Render the Viva report — the override serves the STORED signed
        # PDF bytes (hash block included).
        pdf = request.env['ir.actions.report'].sudo().with_context(
            sale_include_signature=True)._render_qweb_pdf(
                'vivafarm_report.viva_quotation_so', [order_sudo.id])[0]

        # (d) Post the signed PDF in the chatter (same as the standard route
        #     but with the Viva bytes).
        order_sudo.message_post(
            attachments=[('%s.pdf' % order_sudo.name, pdf)],
            author_id=(
                order_sudo.partner_id.id
                if request.env.user._is_public()
                else request.env.user.partner_id.id
            ),
            body='Order signed by %s' % name,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

        # Send the VIVA confirmation email (report = viva_quotation_so -> the
        # stored signed PDF is attached). NOT the standard template 21.
        tpl = request.env.ref(
            'vivafarm_report.viva_email_template_order_confirmation',
            raise_if_not_found=False)
        if tpl:
            order_sudo.with_context(force_send=True).message_post_with_source(
                tpl,
                email_layout_xmlid='mail.mail_notification_layout_with_responsible_signature',
                subtype_xmlid='mail.mt_comment',
            )

        return {
            'force_refresh': True,
            'redirect_url': order_sudo.get_portal_url(query_string='&message=sign_ok'),
        }
