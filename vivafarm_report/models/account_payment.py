from odoo import models, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def _get_thai_date_display(self, field_name):
        """Date in Thai receipt style: '26/09/67' (Buddhist Era year = CE + 543).

        Same approach as account.move._get_thai_date_display: day/month via
        the Thai locale, Buddhist Era year appended.
        """
        self.ensure_one()
        value = self[field_name]
        if not value:
            return ''
        from odoo.tools.misc import format_date
        day_month = format_date(self.env, value, lang_code='th_TH', date_format='dd/MM')
        return '%s/%s' % (day_month, (value.year + 543) % 100)

    def _get_payment_receipt_copies(self):
        """Copies to print for a payment receipt (Thai practice: 3 copies).

        Matches the tax invoice triplicate: ต้นฉบับ/สำหรับลูกค้า (Original /
        For Customer) + สำเนา/สำหรับบริษัท (Copy / For Company) + สำเนา/
        สำหรับบัญชี (Copy / For Accounting).
        """
        self.ensure_one()
        return [
            {'key': 'original', 'th_marker': 'ต้นฉบับ', 'en_marker': 'Original', 'th_recipient': 'สำหรับลูกค้า', 'en_recipient': 'For Customer'},
            {'key': 'company',  'th_marker': 'สำเนา',   'en_marker': 'Copy',     'th_recipient': 'สำหรับบริษัท', 'en_recipient': 'For Company'},
            {'key': 'account',  'th_marker': 'สำเนา',   'en_marker': 'Copy',     'th_recipient': 'สำหรับบัญชี', 'en_recipient': 'For Accounting'},
        ]

    def _compute_payment_receipt_title(self):
        """Thai title for the payment receipt report (ใบเสร็จรับเงิน)."""
        for pay in self:
            pay.payment_receipt_title = _('ใบเสร็จรับเงิน') if pay.partner_id.lang == 'th_TH' else _('Payment Receipt')
