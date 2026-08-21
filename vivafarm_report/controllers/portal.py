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
from odoo.addons.account.controllers.portal import PortalAccount

import binascii


class VivaInvoicePortal(PortalAccount):
    """Forward the `message` query param on the invoice portal page.

    The stock account controller (portal_my_invoice_detail →
    _get_page_view_values) only forwards error/warning/success/pid/hash —
    it DROPS `message`. The Accept & Sign Invoice route redirects back with
    `&message=invoice_sign_ok` so the customer sees the green confirmation
    alert (vivafarm_report.account_portal_viva_invoice_message). Without
    this override the alert never renders on the invoice page. (The SO page
    works because the sale controller forwards `message` explicitly.)
    """
    def _invoice_get_page_view_values(self, invoice, access_token, **kwargs):
        values = super()._invoice_get_page_view_values(invoice, access_token, **kwargs)
        if kwargs.get('message'):
            values['message'] = kwargs['message']
        return values


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
        report = request.env['ir.actions.report'].sudo().with_context(
            viva_show_stamp=True)._render_qweb_pdf(
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
        # template.send_mail() creates a real mail.mail — unlike
        # message_post_with_source which posts to chatter only (user report
        # 2026-08-20: SO email also never arrived).
        tpl = request.env.ref(
            'vivafarm_report.viva_email_template_order_confirmation',
            raise_if_not_found=False)
        if tpl:
            tpl.sudo().send_mail(
                order_sudo.id,
                force_send=True,
                raise_exception=False,
                email_layout_xmlid='mail.mail_notification_layout_with_responsible_signature',
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
        report = request.env['ir.actions.report'].sudo().with_context(
            viva_show_stamp=True)._render_qweb_pdf(
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

        # Send the customer the signed Delivery Order confirmation email
        # (user instruction 2026-08-20: confirmation email for Delivery
        # order). template.send_mail() creates a real mail.mail with the
        # STORED signed PDF attached.
        tpl = request.env.ref(
            'vivafarm_report.viva_email_template_delivery_acknowledgment',
            raise_if_not_found=False)
        if tpl:
            tpl.sudo().send_mail(
                picking_sudo.id,
                force_send=True,
                raise_exception=False,
                email_layout_xmlid='mail.mail_notification_layout_with_responsible_signature',
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
            # Sent invoices show the seller stamp in the portal preview too.
            report_env = report_env.with_context(viva_show_stamp=True)
            # Single-copy preview — the wrapper renders ONE copy for
            # report_type='html' (portal iframe), keeping PDF as triplicate.
            report = report_env._render_qweb_html(
                invoice_sudo._get_viva_invoice_report().report_name,
                [invoice_sudo.id],
                data={'report_type': 'html'})[0]
            headers = [('Content-Type', 'text/html; charset=utf-8'),
                       ('Content-Length', len(report))]
            return request.make_response(report, headers=headers)
        report = request.env['ir.actions.report'].sudo().with_context(
            viva_show_stamp=True)._render_qweb_pdf(
            invoice_sudo._get_viva_invoice_report().report_name,
            [invoice_sudo.id])[0]
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

    @http.route(['/my/invoices/<int:invoice_id>/receipt_pdf'], type='http',
                auth="public", website=True)
    def portal_invoice_receipt_pdf(self, invoice_id, access_token=None, download=False,
                                   **kw):
        """View the Viva Payment Receipt for a paid invoice.

        Serves the SAME receipt PDF that was emailed to the customer after
        the gateway payment (vivafarm_report.viva_payment_receipt on the
        reconciled payment) — user instruction 2026-08-20: the portal
        "View receipt" button opens the same file that was sent by email.
        """
        try:
            invoice_sudo = self._invoice_check_access(invoice_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        payment = invoice_sudo._get_reconciled_payments()[:1]
        if not payment:
            return request.redirect('/my')
        report = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'vivafarm_report.viva_payment_receipt', [payment.id])[0]
        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(report)),
        ]
        if download:
            pdfhttpheaders.append((
                'Content-Disposition',
                'attachment; filename=%s.pdf' % payment.name.replace('/', '_'),
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

        # Render the Viva report — the override serves the STORED signed bytes
        # (the report is the customer's invoice_template_pdf_report_id; a
        # minimal-flow customer's is the TAX invoice, standard is plain).
        viva_report = invoice_sudo._get_viva_invoice_report()
        pdf = request.env['ir.actions.report'].sudo().with_context(
            invoice_include_signature=True)._render_qweb_pdf(
                viva_report.report_name, [invoice_sudo.id])[0]

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

        # Send the customer's copy of the signed invoice (mirrors the SO
        # confirmation email: the template whose report matches the signed
        # document — TAX invoice for minimal-flow customers, plain invoice
        # otherwise — so the STORED signed PDF is attached). template.send_mail()
        # creates a real mail.mail (recipient_ids + signed PDF attachment) —
        # unlike message_post_with_source which posts to chatter only and
        # never generates an outgoing email (user report 2026-08-20).
        tpl_xmlid = ('vivafarm_report.viva_email_template_invoice_acknowledgment_tax'
                     if viva_report.report_name == 'vivafarm_report.viva_invoice'
                     else 'vivafarm_report.viva_email_template_invoice_acknowledgment')
        tpl = request.env.ref(tpl_xmlid, raise_if_not_found=False)
        if tpl:
            tpl.sudo().send_mail(
                invoice_sudo.id,
                force_send=True,
                raise_exception=False,
                email_layout_xmlid='mail.mail_notification_layout_with_responsible_signature',
            )

        return {
            'force_refresh': True,
            'redirect_url': invoice_sudo.get_portal_url(
                query_string='&message=invoice_sign_ok'),
        }

    # ────────────────────────────────────────────────────────────────
    # Manual hand-signed upload (no digital signature) — user flow
    # 2026-08-21. The customer prints, hand-signs, scans, and uploads
    # the signed paper copy back through the token-protected portal.
    # The ERP seals the EXACT uploaded bytes (SHA-256, hash-only, no
    # RSA — same evidence model as the payment receipt) and emails a
    # confirmation containing the /v/<token> verification link.
    #
    # Legal model (Thai law consultant memo 2026-08-21): we claim ONLY
    # (a) these bytes were submitted via the token-linked portal at T,
    # (b) unaltered since (SHA-256), (c) re-checkable anytime. We do NOT
    # claim handwriting/signature authenticity, legal-binding status, or
    # confirmed payment. The typed uploader_name + confirmation checkbox
    # raise ETA B.E.2544 §9/§11 originator weight; IP/UA are retained
    # per §12(3).
    # ────────────────────────────────────────────────────────────────

    _MANUAL_ALLOWED_MIMETYPES = {
        'application/pdf': 'pdf',
        'image/png': 'png',
        'image/jpeg': 'jpg',
    }
    _MANUAL_MAX_SIZE = 10 * 1024 * 1024  # 10 MB

    def _seal_manual_upload(self, record, doc_key, document_type, model,
                            upload, uploader_name, confirm, template_xmlid,
                            document_number=None):
        """Common seal + chatter + email for a manual hand-signed upload.

        Returns a redirect_url (string). The caller redirects there.
        """
        if not upload:
            return self._manual_redirect(record, doc_key, '&message=upload_no_file')
        filename = upload.filename or 'upload'
        mimetype = upload.content_type or 'application/octet-stream'
        data = upload.read()
        if not data:
            # A zero-byte file is not a signed document — reject like a
            # missing file (edge test E7, 2026-08-21).
            return self._manual_redirect(record, doc_key, '&message=upload_no_file')
        if mimetype not in self._MANUAL_ALLOWED_MIMETYPES:
            return self._manual_redirect(record, doc_key, '&message=upload_bad_type')
        if len(data) > self._MANUAL_MAX_SIZE:
            return self._manual_redirect(record, doc_key, '&message=upload_too_large')
        if not uploader_name or not uploader_name.strip():
            return self._manual_redirect(record, doc_key, '&message=upload_name_required')
        if not confirm:
            return self._manual_redirect(record, doc_key, '&message=upload_confirm_required')

        ip = request.httprequest.remote_addr or ''
        ua = (request.httprequest.user_agent or '')[:500]

        signed = request.env['viva.signed.document'].sudo()._create_manual_record(
            model=model,
            record_id=record.id,
            document_type=document_type,
            document_number=document_number or record.name,
            filename=filename,
            mimetype=mimetype,
            data=data,
            uploader_name=uploader_name.strip(),
            uploader_ip=ip,
            uploader_agent=ua,
        )

        # Chatter post — the seller sees the upload with the verify link.
        record.message_post(
            body=('Hand-signed copy received from %s (%s). Verify: %s · Code: %s'
                  % (uploader_name.strip(), filename,
                     signed._get_verification_url(), signed.verification_code)),
            attachments=[(filename, data)],
            author_id=(record.partner_id.id
                       if request.env.user._is_public()
                       else request.env.user.partner_id.id),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

        # Confirmation email — template.send_mail() (real mail.mail), the
        # template body carries the verification link + code (lawyer-approved
        # wording, see the template records).
        tpl = request.env.ref(template_xmlid, raise_if_not_found=False)
        if tpl:
            tpl.sudo().send_mail(
                record.id,
                force_send=True,
                raise_exception=False,
                email_layout_xmlid='mail.mail_notification_layout_with_responsible_signature',
            )

        return self._manual_redirect(record, doc_key, '&message=upload_ok')

    def _manual_redirect(self, record, doc_key, message):
        """Redirect the customer back to the portal page with a status."""
        if doc_key == 'order':
            return record.get_portal_url(query_string=message)
        if doc_key == 'invoice':
            return record.get_portal_url(query_string=message)
        so = record.sale_id
        if so:
            so._portal_ensure_token()
            return so.get_portal_url(query_string=message)
        return '/my'

    @http.route(['/my/orders/<int:order_id>/confirm_viva'], type='http',
                auth="public", website=True, methods=['POST'], csrf=False)
    def portal_order_confirm_manual(self, order_id, access_token=None, **post):
        """Customer uploads the hand-signed quotation/SO paper copy."""
        access_token = access_token or post.get('access_token')
        try:
            order_sudo = self._document_check_access(
                'sale.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        url = self._seal_manual_upload(
            order_sudo, 'order', 'sale_order',
            'sale.order', post.get('upload', ''), post.get('uploader_name', ''),
            post.get('confirm', ''),
            'vivafarm_report.viva_email_template_manual_upload_sale',
            document_number=order_sudo.name,
        )
        return request.redirect(url)

    @http.route(['/my/picking/<int:picking_id>/confirm_viva'], type='http',
                auth="public", website=True, methods=['POST'], csrf=False)
    def portal_picking_confirm_manual(self, picking_id, access_token=None, **post):
        """Route uploads a hand-signed DELIVERY NOTE paper copy."""
        access_token = access_token or post.get('access_token')
        try:
            picking_sudo = self._stock_picking_check_access(picking_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        url = self._seal_manual_upload(
            picking_sudo, 'picking', 'delivery_note', 'stock.picking',
            post.get('upload', ''), post.get('uploader_name', ''),
            post.get('confirm', ''),
            'vivafarm_report.viva_email_template_manual_upload_delivery',
            document_number=picking_sudo.name,
        )
        return request.redirect(url)

    @http.route(['/my/invoices/<int:invoice_id>/confirm_viva'], type='http',
                auth="public", website=True, methods=['POST'], csrf=False)
    def portal_invoice_confirm_manual(self, invoice_id, access_token=None, **post):
        """Route uploads a hand-signed INVOICE (tax/commercial) paper copy."""
        access_token = access_token or post.get('access_token')
        try:
            invoice_sudo = self._invoice_check_access(invoice_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        # The sealed document_type follows the customer's invoice report —
        # 'tax_invoice' for minimal-flow customers, 'invoice' otherwise —
        # exactly like _hash_invoice_accepted and _get_manual_signed_document.
        viva_report = invoice_sudo._get_viva_invoice_report()
        doc_type = ('tax_invoice'
                    if viva_report and viva_report.report_name == 'vivafarm_report.viva_invoice'
                    else 'invoice')
        url = self._seal_manual_upload(
            invoice_sudo, 'invoice', doc_type, 'account.move',
            post.get('upload', ''), post.get('uploader_name', ''),
            post.get('confirm', ''),
            'vivafarm_report.viva_email_template_manual_upload_invoice',
            document_number=invoice_sudo.name,
        )
        return request.redirect(url)
