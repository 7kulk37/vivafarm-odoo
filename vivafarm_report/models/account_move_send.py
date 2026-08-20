"""account.move.send extensions — Send INV (ใบแจ้งหนี้) flow.

The standard Send wizard picks its PDF report via
_account_move_send._get_default_pdf_report_id (partner template → journal
template → account.account_invoices). The "Send INV" button reuses the SAME
wizard (same UX, same is_move_sent marking, same email template) but forces
the custom Viva Invoice (ใบแจ้งหนี้) report through a context flag.

Legal guardrail (lawyer sign-off, 2026-08-19): the commercial invoice is
NOT the tax invoice (ใบกำกับภาษี). The email template stays the standard
account.email_template_edi_invoice — no title change, no penalty language.
"""
from odoo import api, fields, models


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _hook_invoice_document_before_pdf_report_render(self, invoice, invoice_data):
        """Stamp viva_sent_at BEFORE the PDF renders.

        The stock wizard renders the PDF and THEN calls _hook_if_success, so
        stamping there makes the emailed PDF blank while later prints (field
        already set) show the stamp — the exact opposite of the requirement
        (user bug report 2026-08-20). Stamping here puts the Name / Position /
        Date into the PDF that is actually emailed; direct print stays blank
        until the invoice has really been sent.
        """
        res = super()._hook_invoice_document_before_pdf_report_render(invoice, invoice_data)
        if (self.env.context.get('viva_invoice_report')
                and 'email' in invoice_data.get('sending_methods', [])):
            invoice.write({'viva_sent_at': fields.Datetime.now()})
        return res

    def _hook_if_success(self, moves_data, from_cron=False):
        """Stamp viva_sent_at on the invoices that were actually emailed.

        Kept as a fallback for re-sends where the PDF already existed (the
        before-render hook covers the first send; this covers the rest).
        """
        res = super()._hook_if_success(moves_data, from_cron=from_cron)
        for move, move_data in moves_data.items():
            if 'email' in move_data.get('sending_methods', []):
                move.write({'viva_sent_at': fields.Datetime.now()})
        return res

    def _get_default_pdf_report_id(self, move):
        """Return the Viva Invoice (ใบแจ้งหนี้) report when the Send INV
        context flag is set; otherwise keep the standard resolution chain.
        """
        if self.env.context.get('viva_invoice_report'):
            viva_report = self.env.ref(
                'vivafarm_report.report_viva_invoice_plain',
                raise_if_not_found=False,
            )
            if viva_report and move._is_action_report_available(viva_report):
                return viva_report
        return super()._get_default_pdf_report_id(move)
