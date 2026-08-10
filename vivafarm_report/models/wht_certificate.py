from odoo import api, models
from odoo.tools import format_amount


class ReportVivaWhtCertificate(models.AbstractModel):
    """Data model for the WHT Certificate (หนังสือรับรองการหักภาษี ณ ที่จ่าย).

    Pre-computes the WHT rows (tax base + withheld amount per WHT tax line)
    with formatted amounts so the QWeb template stays declarative — the
    same pattern as the tax register / VAT30 data models.

    The income type is derived from the WHT tax NAME by explicit prefix
    matching (the l10n_th tax names follow '3% WH R / A / T / S ...'):
      R -> Rent (ค่าเช่า, Section 40(5))
      A -> Advertising (ค่าบริการโฆษณา, Section 40(8))
      T -> Transport (ค่าขนส่ง, Section 40(8))
      S / fallback -> Service (ค่าบริการ, Section 40(8))
    Prefix matching (not substring) so a tax name like '3% WH C S' cannot
    be misclassified by a stray 'R'/'A'/'T' character in a later word.
    """

    _name = 'report.vivafarm_report.report_viva_wht_certificate'
    _description = 'VivaFarm WHT Certificate Data'

    @api.model
    def _get_income_type(self, tax):
        """Income type label keyed by the tax name's type letter."""
        name = tax.name or ''
        # The type letter sits right after the rate, e.g. '3% WH R ...'.
        if ' R ' in name or name.endswith(' R'):
            return 'rent'
        if ' A ' in name or name.endswith(' A'):
            return 'advertising'
        if ' T ' in name or name.endswith(' T'):
            return 'transport'
        return 'service'

    @api.model
    def _get_wht_lines(self, move):
        """Return WHT lines of a bill: [{tax, rate, base, base_fmt, wht, wht_fmt, income_type}]."""
        currency = move.currency_id or self.env.company.currency_id
        lines = move.line_ids.filtered(
            lambda l: l.tax_line_id and l.tax_line_id.amount < 0)
        rows = []
        for l in lines:
            rows.append({
                'tax': l.tax_line_id.name,
                'rate': -l.tax_line_id.amount,
                'base': l.tax_base_amount,
                'base_fmt': format_amount(self.env, l.tax_base_amount, currency),
                'wht': -l.balance,
                'wht_fmt': format_amount(self.env, -l.balance, currency),
                'income_type': self._get_income_type(l.tax_line_id),
            })
        return rows

    @api.model
    def _get_payment_date(self, move):
        """Date of the bill's payment (the 7-day clock of มาตรา 50 ทวิ starts
        at payment, not at invoice); fall back to the invoice date."""
        if move.payment_state in ('paid', 'in_payment'):
            payments = move._get_reconciled_payments()
            if payments:
                return min(p.date for p in payments)
        return move.invoice_date

    @api.model
    def _get_report_values(self, docids, data=None):
        moves = self.env['account.move'].browse(docids)
        docs = moves
        rows = []
        for m in moves:
            rows.extend(self._get_wht_lines(m))
        currency = moves[0].currency_id or self.env.company.currency_id
        payment_date = moves[0]._get_payment_date() if moves else False
        payment_date_th = False
        if payment_date:
            from odoo.tools.misc import format_date
            day_month = format_date(self.env, payment_date, lang_code='th_TH', date_format='dd/MMM')
            payment_date_th = '%s/%s' % (day_month, payment_date.year + 543)
        return {
            'doc_ids': moves.ids,
            'doc_model': self._name,
            'docs': docs,
            'rows': rows,
            'payment_date': payment_date,
            'payment_date_th': payment_date_th,
            'total_base': format_amount(self.env, sum(r['base'] for r in rows), currency),
            'total_wht': format_amount(self.env, sum(r['wht'] for r in rows), currency),
        }
