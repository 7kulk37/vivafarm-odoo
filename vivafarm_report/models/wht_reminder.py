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
    de_minimis_warning = fields.Boolean(
        string='De-minimis Warning',
        help='Set when the 1,000 THB cumulative per-vendor-per-year threshold '
             'interacts with this payment (VS-08): either WHT was withheld '
             'below the threshold (over-withheld) or the threshold was '
             'crossed without WHT (missed).')
    de_minimis_note = fields.Text(string='De-minimis Note')
    wht_correction = fields.Boolean(
        string='WHT Correction Needed',
        help='Set when a vendor credit note after a paid-and-withheld bill '
             'over-withheld WHT (VS-09, RD Ruling Gor.Kor. 0702/9205). '
             'Operator must: refund the excess to the payee, cancel the '
             'original cert, and file an amended PND for the payment month '
             '(ยื่นเพิ่มเติม). Never net against next month.')
    wht_correction_note = fields.Text(string='WHT Correction Note')

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
        warn, note = self._check_de_minimis(payment, bill)
        reminder = self.create({
            'partner_id': bill.partner_id.id,
            'bill_id': bill.id,
            'payment_id': payment.id,
            'wht_amount': wht_amount,
            'payment_date': payment.date,
            'remit_due': self._compute_remit_due(payment.date),
            'de_minimis_warning': warn,
            'de_minimis_note': note,
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

    @api.model
    def _check_de_minimis(self, payment, bill):
        """Flag 1,000 THB cumulative-rule interactions (VS-08).

        The de-minimis is per-vendor CUMULATIVE per calendar year. Two
        warning cases at payment time:
          - WHT withheld but annual cumulative <= 1,000  -> over-withheld
            (operator should have removed the WHT line)
          - No WHT on the bill but annual cumulative > 1,000 -> missed WHT
            (the threshold was crossed; withholding applies from the
            crossing payment onward)
        Returns a (warning, note) tuple; the operator decides the fix.
        """
        partner = bill.commercial_partner_id
        if not partner or partner.viva_income_type == 'goods':
            return False, ''
        cumulative = partner._cumulative_paid_year(payment.date.year)
        has_wht = bool(bill.line_ids.filtered(
            lambda l: l.tax_line_id and l.tax_line_id.amount < 0))
        if has_wht and cumulative <= 1000.0:
            return True, (
                'WHT withheld on %s but annual cumulative paid to %s is '
                '%.2f (<= 1,000). The 1,000 THB de-minimis is cumulative '
                'per vendor per year — consider removing the WHT line.'
                % (bill.name, partner.name, cumulative))
        if not has_wht and cumulative > 1000.0:
            return True, (
                'No WHT on %s but annual cumulative paid to %s is %.2f '
                '(> 1,000). The 1,000 THB de-minimis is cumulative per '
                'vendor per year — WHT applies from the crossing payment.'
                % (bill.name, partner.name, cumulative))
        return False, ''

    def action_mark_remitted(self):
        for rec in self:
            rec.write({'state': 'remitted', 'remitted_date': fields.Date.context_today(self)})

    @api.model
    def _check_over_withheld(self, credit_note):
        """Flag over-withheld WHT when a credit note reduces a paid bill (VS-09).

        RD Ruling Gor.Kor. 0702/9205 (8 Oct 2015): when WHT was over-withheld
        (e.g. bill 10,000 withheld 300, credit note 2,000 -> correct WHT on
        net 8,000 is 240, excess 60), the payer must refund the excess to the
        payee, cancel the original cert, and file an amended PND for the
        payment month (ยื่นเพิ่มเติม). Never net against next month.

        This is a FLAG for the operator — never auto-cancel certs or auto-file.
        """
        if credit_note.move_type != 'in_refund':
            return
        original = credit_note.reversed_entry_id
        if not original or original.move_type != 'in_invoice':
            return
        # Only when the original was paid (WHT was actually withheld).
        reminder = self.search([
            ('bill_id', '=', original.id),
            ('state', '=', 'pending'),
        ], limit=1)
        if not reminder or not reminder.wht_amount:
            return
        # Recompute WHT on the net-of-credit-note amount. in_refund moves
        # have POSITIVE amount_total in Odoo 19 (sign lives in lines).
        net = original.amount_total - credit_note.amount_total
        wht_tax = original.line_ids.filtered(
            lambda l: l.tax_line_id and l.tax_line_id.amount < 0)
        if not wht_tax:
            return
        rate = -wht_tax[0].tax_line_id.amount
        # price_include=True grosses up: base = net / (1 - rate), tax = base * rate.
        correct_wht = net * rate / (1 - rate) if wht_tax[0].tax_line_id.price_include else net * rate
        excess = reminder.wht_amount - correct_wht
        if excess > 0.01:
            reminder.write({
                'wht_correction': True,
                'wht_correction_note': (
                    'Credit note %s reduces bill %s. WHT withheld %.2f, '
                    'correct on net %.2f is %.2f — excess %.2f. Refund the '
                    'excess to the payee, cancel the original cert, and file '
                    'an amended PND for the payment month (ยื่นเพิ่มเติม). '
                    'Never net against next month (RD Ruling Gor.Kor. 0702/9205).'
                    % (credit_note.name, original.name, reminder.wht_amount,
                       net, correct_wht, excess)),
            })
