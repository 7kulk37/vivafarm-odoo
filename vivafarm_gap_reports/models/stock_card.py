from odoo import api, models


class ReportStockCard(models.AbstractModel):
    """Data model for the Stock Card (AVCO) report.

    Per-product report bound to ``product.product``. Rows come from the
    ``stock.avco.report`` model (AVCO module's running valuation view),
    sorted chronologically, with a running quantity/value balance and
    unit cost computed in Python.
    """

    _name = 'report.vivafarm_gap_reports.report_stock_card'
    _description = 'Stock Card Report Data'

    @api.model
    def _get_report_values(self, docids, data=None):
        products = self.env['product.product'].browse(docids).exists()
        rows = []
        for product in products:
            avco = self.env['stock.avco.report'].search(
                [('product_id', '=', product.id)], order='date, id')
            card_rows = []
            running_qty = 0.0
            running_value = 0.0
            for a in avco:
                running_qty += a.quantity
                running_value += a.value
                card_rows.append({
                    'date': a.date,
                    'reference': a.reference or '',
                    'description': a.description or '',
                    'qty': round(a.quantity, 2),
                    'value': round(a.value, 2),
                    'running_qty': round(running_qty, 2),
                    'running_value': round(running_value, 2),
                    'unit_cost': (running_value / running_qty) if running_qty else 0.0,
                })
            rows.append({
                'product': product,
                'name': product.name,
                'default_code': product.default_code or '',
                'uom': product.uom_id.name or '',
                'rows': card_rows,
                'total_qty': running_qty,
                'total_value': running_value,
            })
        return {
            'doc_ids': products.ids,
            'doc_model': self._name,
            'docs': products,
            'rows': rows,
        }
