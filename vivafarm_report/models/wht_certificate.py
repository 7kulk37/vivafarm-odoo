from odoo import api, models
from odoo.tools import format_amount


class ReportVivaWhtCertificate(models.AbstractModel):
    """Data model for the WHT Certificate (หนังสือรับรองการหักภาษี ณ ที่จ่าย).

    Pre-computes the WHT rows (tax base + withheld amount per WHT tax line)
    with formatted amounts so the QWeb template stays declarative — the
    same pattern as the tax register / VAT30 data models.
    """

    _name = 'report.vivafarm_report.report_viva_wht_certificate'
    _description = 'VivaFarm WHT Certificate Data'

    @api.model
    def _get_wht_lines(self, move):
        """Return WHT lines of a bill: [{tax, rate, base, base_fmt, wht, wht_fmt}]."""
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
            })
        return rows

    @api.model
    def _get_report_values(self, docids, data=None):
        moves = self.env['account.move'].browse(docids)
        docs = moves
        rows = []
        for m in moves:
            rows.extend(self._get_wht_lines(m))
        currency = moves[0].currency_id or self.env.company.currency_id
        return {
            'doc_ids': moves.ids,
            'doc_model': self._name,
            'docs': docs,
            'rows': rows,
            'total_base': format_amount(self.env, sum(r['base'] for r in rows), currency),
            'total_wht': format_amount(self.env, sum(r['wht'] for r in rows), currency),
        }
