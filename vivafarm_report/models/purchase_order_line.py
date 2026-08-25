from odoo import models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _compute_tax_id(self):
        """Auto-suggest the vendor's default WHT tax (VS-01).

        super() computes the product's supplier taxes (goods purchases).
        For a vendor classified with a non-goods income type (rent /
        transport / service / advertising), append the vendor's default
        WHT tax so the PO line — and the bill created from it — carries
        the correct withholding. Goods vendors (default) get nothing:
        sale of goods is not on the WHT list.
        """
        super()._compute_tax_id()
        for line in self:
            partner = line.order_id.partner_id
            wht = partner.viva_default_wht_tax_id
            if wht and wht.id not in line.tax_ids.ids:
                line.tax_ids = [(4, wht.id)]
