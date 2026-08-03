from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_tax_invoice_copies(self):
        """Copies to print for a tax invoice (Thai practice: 3 copies).

        Only posted customer invoices (ใบกำกับภาษี) print 3 copies; all other
        documents print a single copy without the copy badge.
        """
        self.ensure_one()
        if self.move_type == 'out_invoice' and self.state == 'posted':
            return [
                {'key': 'original', 'th_marker': 'ต้นฉบับ', 'en_marker': 'Original', 'th_recipient': 'สำหรับลูกค้า', 'en_recipient': 'For Customer'},
                {'key': 'company',  'th_marker': 'สำเนา',   'en_marker': 'Copy',     'th_recipient': 'สำหรับบริษัท', 'en_recipient': 'For Company'},
                {'key': 'account',  'th_marker': 'สำเนา',   'en_marker': 'Copy',     'th_recipient': 'สำหรับบัญชี', 'en_recipient': 'For Accounting'},
            ]
        return [{'key': False, 'th_marker': '', 'en_marker': '', 'th_recipient': '', 'en_recipient': ''}]

    def _get_tax_invoice_totals(self):
        """Rows for the Thai tax-invoice totals table (bilingual).

        Follows Thai practice (RD sec. 86/4 + common layouts, cf. the
        reference invoice): TOTAL AMOUNT, DISCOUNT (when any), VAT rows with
        rate (or an explicit VAT-exempt line), GRAND TOTAL.

        Withholding-tax groups are excluded: WHT is an income-tax matter
        handled by the buyer with a separate certificate, never shown on a
        seller's VAT tax invoice.
        """
        self.ensure_one()
        tt = self.tax_totals or {}
        lines = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        gross_total = sum(l.price_unit * l.quantity for l in lines)
        discount = sum(l.price_unit * l.quantity * (l.discount or 0.0) / 100.0 for l in lines)
        net_total = tt.get('base_amount_currency', gross_total - discount)
        vat_rows = []
        exempt_rows = []
        for subtotal in tt.get('subtotals') or []:
            for group in subtotal.get('tax_groups') or []:
                if 'WHT' in (group.get('group_name') or '').upper():
                    continue  # withholding tax: not shown on a VAT tax invoice
                taxes = self.env['account.tax'].browse(group.get('involved_tax_ids') or [])
                label = ', '.join(t.name for t in taxes) or group.get('group_name') or ''
                amount = group.get('tax_amount_currency') or 0.0
                if amount:
                    rate = max((t.amount for t in taxes if t.amount_type in ('percent', 'division')),
                               default=None)
                    vat_rows.append({'rate_label': ('%g%%' % rate) if rate is not None else '',
                                     'amount': amount})
                elif label:
                    exempt_rows.append({'label': label})
        return {
            'gross_total': gross_total,
            'discount': discount,
            'net_total': net_total,
            'vat_rows': vat_rows,
            'exempt_rows': exempt_rows,
            'is_exempt': not vat_rows,
            'grand_total': tt.get('total_amount_currency', net_total),
        }
