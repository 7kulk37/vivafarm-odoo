from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _compute_tax_ids(self):
        """Auto-suggest the vendor's default WHT tax on direct vendor bills (VS-01).

        super() computes taxes from the product's supplier taxes / the
        account's taxes. For a direct vendor bill (no PO) with a vendor
        classified as rent / transport / service / advertising, append the
        vendor's default WHT tax — but ONLY when the line has no explicit
        taxes yet, so a deliberate user override (or a goods line with its
        own VAT) is never overwritten. Goods vendors (default) add nothing:
        sale of goods is not on the WHT list.
        """
        super()._compute_tax_ids()
        for line in self:
            if line.display_type in ('line_section', 'line_subsection', 'line_note', 'payment_term', 'cogs'):
                continue
            if not line.move_id.is_purchase_document(include_receipts=True):
                continue
            if line.tax_ids:
                # Explicit taxes already present (user override, product
                # VAT, or a previous suggestion) — do not fight them.
                continue
            wht = line.partner_id.viva_default_wht_tax_id
            if wht:
                line.tax_ids = [(4, wht.id)]
