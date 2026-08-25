from odoo import api, fields, models


class VivaWhtReminder(models.Model):
    """WHT remittance reminder (VS-05).

    Created when a vendor bill carrying WHT tax lines is paid. The
    withholding obligation is incurred at payment (มาตรา 50); the withheld
    tax must be remitted with the monthly ภ.ง.ด.3/53 return by the 7th of
    the following month (15th with e-filing, mandatory since 1-Jan-2025 —
    the e-filing extension applies to the remittance because it is filed
    together with the return per มาตรา 59). The reminder's remit_due is the
    15th of the month following the payment month (e-filing deadline).

    The WHT certificate (ใบรับรองหักภาษี ณ ที่จ่าย) is generated at the same
    time (มาตรา 50 ทวิ — issue "immediately" at payment) and attached to
    the payment.
    """

    _name = 'viva.wht.reminder'
    _description = 'WHT Remittance Reminder'
    _order = 'remit_due asc, id desc'

    partner_id = fields.Many2one('res.partner', string='Payee', required=True)
    bill_id = fields.Many2one('account.move', string='Vendor Bill', required=True)
    payment_id = fields.Many2one('account.payment', string='Payment', required=True)
    wht_amount = fields.Monetary(string='WHT Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)
    payment_date = fields.Date(string='Payment Date', required=True)
    remit_due = fields.Date(string='Remit Due (15th e-filing)', required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('remitted', 'Remitted'),
    ], string='State', default='pending')
    remitted_date = fields.Date(string='Remitted Date')

    @api.model
    def _compute_remit_due(self, payment_date):
        """15th of the month following the payment month (e-filing deadline)."""
        from datetime import date
        if payment_date.month == 12:
            return date(payment_date.year + 1, 1, 15)
        return date(payment_date.year, payment_date.month + 1, 15)

    @api.model
    def _create_for_payment(self, payment, bill):
        """Create the WHT reminder for a paid bill (idempotent per payment+bill).

        Also attaches the generated WHT certificate PDF to the payment so
        the operator can print/send it immediately (มาตรา 50 ทวิ — issue
        "immediately" at payment).
        """
        existing = self.search([
            ('payment_id', '=', payment.id),
            ('bill_id', '=', bill.id),
        ], limit=1)
        if existing:
            return existing
        wht_lines = bill.line_ids.filtered(
            lambda l: l.tax_line_id and l.tax_line_id.amount < 0)
        wht_amount = sum(-l.balance for l in wht_lines)
        reminder = self.create({
            'partner_id': bill.partner_id.id,
            'bill_id': bill.id,
            'payment_id': payment.id,
            'wht_amount': wht_amount,
            'payment_date': payment.date,
            'remit_due': self._compute_remit_due(payment.date),
        })
        # Attach the WHT certificate PDF to the payment (one per bill).
        try:
            # Render by report NAME (string), not the action record — the
            # l10n_th _pre_render_qweb_pdf override calls _get_report on the
            # ref and a record object breaks the cache key (unhashable list).
            pdf = self.env['ir.actions.report']._render_qweb_pdf(
                'vivafarm_report.report_viva_wht_certificate', [bill.id])[0]
            self.env['ir.attachment'].create({
                'name': 'WHT_Cert_%s.pdf' % (bill.name or bill.id),
                'res_model': 'account.payment',
                'res_id': payment.id,
                'type': 'binary',
                'mimetype': 'application/pdf',
                'raw': pdf,
            })
        except Exception:
            # Certificate render failure must not block the payment.
            pass
        return reminder

    def action_mark_remitted(self):
        for rec in self:
            rec.write({'state': 'remitted', 'remitted_date': fields.Date.context_today(self)})
