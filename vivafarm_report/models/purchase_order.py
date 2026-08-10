from odoo import models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _get_thai_date_display(self, field_name):
        """Date in Thai tax-invoice style: '03/ส.ค./2569' (Buddhist Era year = CE + 543).

        Mirrors account.move._get_thai_date_display so the PO's TH form uses
        the same date format as the tax invoice. Babel has no Buddhist
        calendar engine, so day/month come from the Thai locale (dd/MMM ->
        '03/ส.ค.') and the Buddhist Era year (Gregorian + 543) is appended.
        """
        self.ensure_one()
        value = self[field_name]
        if not value:
            return ''
        from odoo.tools.misc import format_date
        day_month = format_date(self.env, value, lang_code='th_TH', date_format='dd/MMM')
        return '%s/%s' % (day_month, value.year + 543)
