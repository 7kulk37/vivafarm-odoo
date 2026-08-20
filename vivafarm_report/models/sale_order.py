from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    signed_position = fields.Char(
        string='Signed Position',
        help='Position of the person who accepted and signed the quotation on the portal.',
    )

    #: When the quotation was emailed to the customer (Sent Quotation wizard,
    #: mark_so_as_sent). The Authorized Signatory box stamps Name / Position /
    #: Date ONLY when this is set — a direct print leaves the box blank
    #: (user instruction 2026-08-20).
    viva_sent_at = fields.Datetime(string='Sent At (Viva)', copy=False)

    def _get_thai_date_display(self, field_name):
        """Date in Thai tax-invoice style: '03/ส.ค./2569' (Buddhist Era year = CE + 543).

        Mirrors account.move._get_thai_date_display so the Quotation/SO's TH
        form uses the same date format as the tax invoice.
        """
        self.ensure_one()
        value = self[field_name]
        if not value:
            return ''
        from odoo.tools.misc import format_date
        day_month = format_date(self.env, value, lang_code='th_TH', date_format='dd/MMM')
        return '%s/%s' % (day_month, value.year + 543)

    def _get_viva_datetime_display(self, field_name):
        """Datetime in the report sign-section style: '2026-08-20 23:23:51'
        (Bangkok local, Asia/Bangkok UTC+7).

        `signed_on` / `viva_sent_at` are stored UTC; the report must show the
        local wall-clock time the customer sees, not the UTC value.
        """
        self.ensure_one()
        value = self[field_name]
        if not value:
            return ''
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        utc = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return utc.astimezone(ZoneInfo('Asia/Bangkok')).strftime('%Y-%m-%d %H:%M:%S')

    def message_post(self, **kwargs):
        """Stamp viva_sent_at when the Sent Quotation wizard marks the SO sent.

        The Authorized Signatory box on the report shows Name / Position /
        Date ONLY when the document was actually emailed to the customer
        (user instruction 2026-08-20) — a direct print stays blank.
        """
        if self.env.context.get('mark_so_as_sent'):
            self.filtered(lambda o: o.state == 'draft').write({
                'viva_sent_at': fields.Datetime.now(),
            })
        return super().message_post(**kwargs)

    def action_sent_quotation(self):
        """Same as action_quotation_send but attaches the Viva custom report.

        Opens the mail.compose.message wizard with the Viva "Sent Quotation"
        email template (which carries vivafarm_report.viva_quotation_so as
        its report attachment) instead of the standard saleorder report.
        Keeps mark_so_as_sent so sending moves the SO draft -> sent.
        """
        self.filtered(lambda so: so.state in ('draft', 'sent')).order_line._validate_analytic_distribution()

        ctx = {
            'default_model': 'sale.order',
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'email_notification_allow_footer': True,
            'hide_mail_template_management_options': True,
            'proforma': self.env.context.get('proforma', False),
        }

        if len(self) > 1:
            ctx['default_composition_mode'] = 'mass_mail'
        else:
            ctx.update({
                'force_email': True,
            })
            mail_template = self.env.ref(
                'vivafarm_report.viva_email_template_sent_quotation',
                raise_if_not_found=False,
            )
            if mail_template:
                ctx.update({
                    'default_template_id': mail_template.id,
                    'mark_so_as_sent': True,
                })
            else:
                for order in self:
                    order._portal_ensure_token()

        return {
            'name': _('Sent Quotation'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }
