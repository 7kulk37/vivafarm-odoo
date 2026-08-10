from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_thai_date_display(self, field_name):
        """Date in Thai tax-invoice style: '03/ส.ค./2569' (Buddhist Era year = CE + 543).

        Same helper as account.move._get_thai_date_display — the delivery
        note (ใบส่งสินค้า) renders its dates in the same Thai format.
        """
        self.ensure_one()
        value = self[field_name]
        if not value:
            return ''
        from odoo.tools.misc import format_date
        day_month = format_date(self.env, value, lang_code='th_TH', date_format='dd/MMM')
        return '%s/%s' % (day_month, value.year + 543)
