from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = ['sale.order', 'viva.report.mixin']

    signed_position = fields.Char(
        string='Signed Position',
        help='Position of the person who accepted and signed the quotation on the portal.',
    )

    #: When the quotation was emailed to the customer (Sent Quotation wizard,
    #: mark_so_as_sent). The Authorized Signatory box stamps Name / Position /
    #: Date ONLY when this is set — a direct print leaves the box blank
    #: (user instruction 2026-08-20).
    viva_sent_at = fields.Datetime(string='Sent At (Viva)', copy=False)

    def _get_manual_signed_document(self):
        """The manual hand-signed upload sealed for this order, if any.

        Manual uploads (channel='manual', user flow 2026-08-21) carry the
        verification link/code the confirmation email references. Digital
        signatures seal through vivafarm_document_sign._hash_customer_accepted
        instead. Lives HERE (vivafarm_report loads before vivafarm_document_sign)
        so the email templates render during module load — must be defensive:
        the viva.signed.document model does NOT exist yet when the report
        module's own templates are render-checked at load time.
        """
        try:
            Model = self.env['viva.signed.document']
        except KeyError:
            return None
        return Model.sudo().search([
            ('sale_order_id', '=', self.id),
            ('document_type', '=', 'sale_order'),
            ('channel', '=', 'manual'),
        ], limit=1)

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
