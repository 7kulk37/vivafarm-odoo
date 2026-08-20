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

import binascii


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
                                 signature=None, position=None):
        # Same access + preconditions as the standard accept route.
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            order_sudo = self._document_check_access(
                'sale.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return {'error': 'Invalid order.'}

        # Idempotency (bug 2, user report 2026-08-17): the route can be hit
        # twice by a double-fire / stale re-click / SERIALIZATION_FAILURE
        # retry. The loser arrives after the winner committed: the order is
        # already signed and confirmed. Treat that as a benign success
        # (force_refresh + sign_ok) instead of the stock guard error — the
        # customer accepted the quotation; the second click must not look
        # like a failure. Checked BEFORE _has_to_be_signed(): once the
        # winner confirms the order, the guard would fire the stock error.
        if order_sudo.state == 'sale' and order_sudo.signature:
            return {
                'force_refresh': True,
                'redirect_url': order_sudo.get_portal_url(
                    query_string='&message=sign_ok'),
            }

        if not order_sudo._has_to_be_signed():
            return {'error': 'The order is not in a state requiring customer signature.'}
        if not signature:
            return {'error': 'Signature is missing.'}

        try:
            order_sudo.write({
                'signed_by': name,
                'signed_position': position or False,
                'signed_on': fields.Datetime.now(),
                'signature': signature,
            })
            # flush now to make signature data available to PDF render request
            request.env.cr.flush()
        except (TypeError, binascii.Error):
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

    def _stock_picking_check_access(self, picking_id, access_token=None):
        """Access check for a picking via its linked SO's portal token.

        Mirrors sale_stock/controllers/portal.py: a picking is reachable
        through the customer's order portal when the caller has the SO's
        access_token (or read rights on the picking itself).
        """
        picking = request.env['stock.picking'].browse([picking_id])
        picking_sudo = picking.sudo()
        try:
            picking.check_access('read')
        except AccessError:
            if not access_token or not picking_sudo.sale_id or \
                    access_token != picking_sudo.sale_id.access_token:
                raise
        return picking_sudo

    @http.route(['/my/picking/<int:picking_id>/viva_pdf'], type='http',
                auth="public", website=True)
    def portal_picking_viva_pdf(self, picking_id, access_token=None, download=False, **kw):
        """View the custom Viva delivery note (ใบส่งสินค้า).

        Standard portal delivery link (/my/picking/pdf/<id>) renders the
        DEFAULT stock.action_report_delivery. This route renders the custom
        vivafarm_report.viva_delivery_note — and once the customer has
        acknowledged receipt, the ir_actions_report override serves the
        STORED signed bytes (hash block included).
        """
        try:
            picking_sudo = self._stock_picking_check_access(picking_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        report = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'vivafarm_report.viva_delivery_note', [picking_sudo.id])[0]
        # stock.picking has no _get_report_base_filename() (the standard
        # sale_stock delivery route builds headers manually too).
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(report)),
        ]
        if download:
            pdfhttpheaders.append((
                'Content-Disposition',
                'attachment; filename=%s.pdf' % picking_sudo.name.replace('/', '_'),
            ))
        return request.make_response(report, headers=pdfhttpheaders)

    @http.route(['/my/picking/<int:picking_id>/accept_viva'], type='jsonrpc',
                auth="public", website=True)
    def portal_picking_accept_viva(self, picking_id, access_token=None, name=None,
                                   signature=None, position=None):
        """Customer acknowledges receipt of a delivery (ใบส่งสินค้า).

        Same 3-layer guard design as /accept_viva:
          1. Server idempotency — a repeat POST on an already-signed picking
             is a benign success (force_refresh + sign_ok), checked BEFORE
             the state guard.
          2. Customer-side JS one-shot lock (accept_viva_guard.js).
          3. DB UNIQUE(picking_id) constraint + IntegrityError convergence
             in _hash_delivery_accepted.
        Writes the customer's drawn signature + name + position on the
        picking, hashes the delivery note (baking the receiver signature in
        via delivery_include_signature), posts the signed PDF in the
        chatter. No confirmation email — the customer has the goods
        physically (user decision 2026-08-18).
        """
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            picking_sudo = self._stock_picking_check_access(picking_id, access_token=access_token)
        except (AccessError, MissingError):
            return {'error': 'Invalid delivery note.'}

        # Idempotency: already signed (customer signed -> flag cleared ->
        # state done) -> benign success.
        if picking_sudo.state == 'done' and picking_sudo.signature:
            return {
                'force_refresh': True,
                'redirect_url': self._delivery_redirect_url(picking_sudo),
            }

        # The customer can only sign an IN TRANSIT delivery (user design
        # 2026-08-18: Ready > In Transit > Done). 'done' without signature
        # means Path A (Validate) or Force Done — signing is meaningless.
        if picking_sudo.state != 'in_transit':
            return {'error': 'The delivery note is not in transit.'}
        if not signature:
            return {'error': 'Signature is missing.'}

        try:
            picking_sudo.write({
                'signed_by': name,
                'signed_position': position or False,
                'signed_on': fields.Datetime.now(),
                'signature': signature,
            })
            # flush now to make signature data available to PDF render request
            request.env.cr.flush()
        except (TypeError, binascii.Error):
            return {'error': 'Invalid signature data.'}

        # Complete the delivery the way Validate would (clears in_transit,
        # moves stock, state -> done), THEN hash the acknowledged DN.
        picking_sudo._complete_delivery()

        # Hash the acknowledged delivery note (receiver signature baked in).
        picking_sudo.with_context(delivery_include_signature=True)._hash_delivery_accepted()

        # Render the Viva report — the override serves the STORED signed bytes.
        pdf = request.env['ir.actions.report'].sudo().with_context(
            delivery_include_signature=True)._render_qweb_pdf(
                'vivafarm_report.viva_delivery_note', [picking_sudo.id])[0]

        # Post the signed PDF in the chatter.
        picking_sudo.message_post(
            attachments=[('%s.pdf' % picking_sudo.name, pdf)],
            author_id=(
                picking_sudo.partner_id.id
                if request.env.user._is_public()
                else request.env.user.partner_id.id
            ),
            body='Delivery received by %s' % name,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

        return {
            'force_refresh': True,
            'redirect_url': self._delivery_redirect_url(picking_sudo),
        }

    def _delivery_redirect_url(self, picking):
        """Where the customer lands after acknowledging a delivery.

        stock.picking has no portal.mixin / get_portal_url — deliveries live
        on the linked SO's portal page, so redirect there (with the sign_ok
        message like the SO flow). Fall back to /my when no SO link.
        """
        so = picking.sale_id
        if so:
            so._portal_ensure_token()
            return so.get_portal_url(query_string='&message=delivery_sign_ok')
        return '/my'

    def _invoice_check_access(self, invoice_id, access_token=None):
        """Access check for an invoice via its portal token.

        Mirrors account/controllers/portal.py: an invoice is reachable
        through the customer's portal when the caller has the invoice's
        access_token (or read rights on the invoice itself).
        """
        invoice = request.env['account.move'].browse([invoice_id])
        invoice_sudo = invoice.sudo()
        try:
            invoice.check_access('read')
        except AccessError:
            if not access_token or access_token != invoice_sudo.access_token:
                raise
        return invoice_sudo

    @http.route(['/my/invoices/<int:invoice_id>/viva_pdf'], type='http',
                auth="public", website=True)
    def portal_invoice_viva_pdf(self, invoice_id, access_token=None, download=False,
                                report_type='pdf', **kw):
        """View the custom Viva Invoice (ใบแจ้งหนี้) PDF (or HTML preview).

        Standard portal invoice iframe/download renders the DEFAULT report
        (account.account_invoices or the partner's invoice_template_pdf_report_id).
        This route renders the custom vivafarm_report.viva_invoice_plain —
        and once the customer has acknowledged it, the ir_actions_report
        override serves the STORED signed bytes (hash block included).

        `report_type='html'` is used by the portal iframe (above the
        Communication history) so the on-page preview shows the same Viva
        Invoice — with the customer signature baked in after acknowledgment.
        """
        try:
            invoice_sudo = self._invoice_check_access(invoice_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        if report_type == 'html':
            report_env = request.env['ir.actions.report'].sudo()
            # After acknowledgment, bake the customer's drawn signature into
            # the on-page preview (mirrors the PDF's invoice_include_signature).
            if invoice_sudo.signature:
                report_env = report_env.with_context(invoice_include_signature=True)
            # Single-copy preview (not the stacked 3-copy triplicate) — the
            # portal iframe should look like a printed page, not a long stack.
            report_env = report_env.with_context(viva_portal_preview=True)
            report = report_env._render_qweb_html(
                'vivafarm_report.viva_invoice_plain', [invoice_sudo.id])[0]
            headers = [('Content-Type', 'text/html; charset=utf-8'),
                       ('Content-Length', len(report))]
            return request.make_response(report, headers=headers)
        report = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'vivafarm_report.viva_invoice_plain', [invoice_sudo.id])[0]
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(report)),
        ]
        if download:
            pdfhttpheaders.append((
                'Content-Disposition',
                'attachment; filename=%s.pdf' % invoice_sudo.name.replace('/', '_'),
            ))
        return request.make_response(report, headers=pdfhttpheaders)

    @http.route(['/my/invoices/<int:invoice_id>/accept_viva'], type='jsonrpc',
                auth="public", website=True)
    def portal_invoice_accept_viva(self, invoice_id, access_token=None, name=None,
                                   signature=None, position=None):
        """Customer acknowledges an invoice (ใบแจ้งหนี้) — EVIDENCE-ONLY.

        Lawyer sign-off (2026-08-19): the acknowledgment is optional and
        never gates payment. This route writes the customer's drawn
        signature + name + position on the invoice, then hashes + stores
        the signed invoice PDF (vivafarm_document_sign). Refusal is NOT a
        state — the invoice stays posted/not_paid; the seller records the
        dispute in the chatter.

        Same 3-layer guard design as /accept_viva:
          1. Server idempotency — a repeat POST on an already-signed
             invoice is a benign success (force_refresh + sign_ok).
          2. Customer-side JS one-shot lock (accept_viva_guard.js).
          3. DB UNIQUE(move_id) constraint + IntegrityError convergence
             in _hash_invoice_accepted.
        """
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            invoice_sudo = self._invoice_check_access(invoice_id, access_token=access_token)
        except (AccessError, MissingError):
            return {'error': 'Invalid invoice.'}

        # Idempotency: already signed -> benign success.
        if invoice_sudo._is_signed():
            return {
                'force_refresh': True,
                'redirect_url': invoice_sudo.get_portal_url(
                    query_string='&message=invoice_sign_ok'),
            }

        if invoice_sudo.state != 'posted':
            return {'error': 'The invoice is not in a state requiring acknowledgment.'}
        if not signature:
            return {'error': 'Signature is missing.'}

        try:
            invoice_sudo.write({
                'signed_by': name,
                'signed_position': position or False,
                'signed_on': fields.Datetime.now(),
                'signature': signature,
            })
            # flush now to make signature data available to PDF render request
            request.env.cr.flush()
        except (TypeError, binascii.Error):
            return {'error': 'Invalid signature data.'}

        # Hash the acknowledged invoice (customer signature baked in).
        invoice_sudo.with_context(invoice_include_signature=True)._hash_invoice_accepted()

        # Render the Viva report — the override serves the STORED signed bytes.
        pdf = request.env['ir.actions.report'].sudo().with_context(
            invoice_include_signature=True)._render_qweb_pdf(
                'vivafarm_report.viva_invoice_plain', [invoice_sudo.id])[0]

        # Post the signed PDF in the chatter.
        invoice_sudo.message_post(
            attachments=[('%s.pdf' % invoice_sudo.name, pdf)],
            author_id=(
                invoice_sudo.partner_id.id
                if request.env.user._is_public()
                else request.env.user.partner_id.id
            ),
            body='Invoice acknowledged by %s' % name,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

        return {
            'force_refresh': True,
            'redirect_url': invoice_sudo.get_portal_url(
                query_string='&message=invoice_sign_ok'),
        }
