"""mail.compose.message extension — stamp viva_sent_at at ACTUAL SEND time and
regenerate the emailed PDF so it carries the seller stamp (user bug report
2026-08-21, second pass).

The mail.compose.message wizard renders the report PDF attachment inside
_compute_attachment_ids when the wizard OPENS (single-record comment mode).
v158 stamped there — that made the stamp appear on a bare print once the user
had merely OPENED the wizard, without sending. The stamp must only be written
when the user actually clicks Send, and the wizard's attachment bytes must be
re-rendered at that instant, because the emailed PDF is the bytes generated at
wizard-open.

This override hooks _action_send_mail_comment: for the Viva Sent Quotation
template it stamps the draft SO(s) and re-renders the wizard's report
attachment with the STAMPED PDF, then lets the normal send path attach those
bytes to the customer email. A direct print (never sent) stays blank; the
emailed PDF carries the seller Name / Position / Date.
"""

import base64

from odoo import fields, models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _action_send_mail_comment(self, res_ids):
        """Stamp viva_sent_at and regenerate the emailed PDF at SEND time.

        Runs when the user clicks Send in the Sent Quotation wizard — AFTER
        the wizard opened (attachment already generated blank) but BEFORE the
        mail message is posted, so the emailed bytes are the stamped render.
        """
        viva_tpl = self.env.ref(
            'vivafarm_report.viva_email_template_sent_quotation',
            raise_if_not_found=False,
        )
        if (
            viva_tpl
            and self.template_id == viva_tpl
            and self.model == 'sale.order'
            and self.composition_mode == 'comment'
        ):
            orders = self.env['sale.order'].browse(res_ids).filtered(
                lambda o: o.state == 'draft' and not o.viva_sent_at
            )
            if orders:
                orders.write({'viva_sent_at': fields.Datetime.now()})
                report = self.env.ref(
                    'vivafarm_report.action_report_viva_quotation_so',
                    raise_if_not_found=False,
                )
                if report:
                    for order in orders:
                        pdf = report.with_context(debug=False)._render_qweb_pdf(
                            report.report_name, order.ids,
                        )[0]
                        att = self.attachment_ids.filtered(
                            lambda a: a.res_model == 'mail.compose.message'
                            and a.res_id == 0
                        )[:1]
                        if att:
                            att.write({
                                'datas': base64.b64encode(pdf),
                                'name': 'Quotation - %s.pdf' % order.name,
                            })
        return super()._action_send_mail_comment(res_ids)
