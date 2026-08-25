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

        Future-VAT flip (VS-14): when the company is VAT-registered and the
        bill date is on/after both the company's registration date and the
        vendor's VAT_registered_since, swap the non-recoverable purchase VAT
        for the recoverable one (forward-only — pre-registration bills keep
        non-recoverable treatment; no retroactive claims, มาตรา 82/5).
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

    def _apply_vat_flip(self):
        """Swap non-recoverable -> recoverable purchase VAT (VS-14).

        Called from account.move._post() before posting, so the bill date
        and company/vendor flags are final. Forward-only: bills dated
        before the company's registration date or the vendor's
        VAT_registered_since keep non-recoverable treatment (มาตรา 82/5 —
        no retroactive input claims).
        """
        for line in self:
            if line.display_type in ('line_section', 'line_subsection', 'line_note', 'payment_term', 'cogs'):
                continue
            if not line.move_id.is_purchase_document(include_receipts=True):
                continue
            company = line.company_id
            if not company.viva_vat_registered:
                continue
            bill_date = line.move_id.invoice_date or line.move_id.date
            if not bill_date:
                continue
            since = company.viva_vat_registered_since
            vendor_since = line.partner_id.viva_vat_registered_since
            if since and bill_date < since:
                continue
            # The vendor must be KNOWN VAT-registered (has a
            # VAT_registered_since date) and the bill dated on/after it —
            # otherwise no input credit (มาตรา 82/5: no credit on invoices
            # from non-registered vendors).
            if not vendor_since or bill_date < vendor_since:
                continue
            nr = self.env['account.tax'].search([
                ('name', '=', 'Purchase Non-Recoverable VAT 7%'),
                ('type_tax_use', '=', 'purchase'),
            ], limit=1)
            if not nr or nr.id not in line.tax_ids.ids:
                continue
            rec = company._get_recoverable_purchase_vat_tax()
            line.tax_ids = [(3, nr.id), (4, rec.id)]
