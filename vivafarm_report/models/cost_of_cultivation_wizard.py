from datetime import timedelta

from odoo import api, fields, models
from odoo.tools import format_amount


class CostOfCultivationWizard(models.TransientModel):
    """Period picker for the Cost of Cultivation management report.

    Standard Odoo wizard→report pattern (same as tax.report.wizard): the
    wizard stores the period, the Print button opens the QWeb report bound
    to this model, and the report data model
    (report.vivafarm_report.report_cost_of_cultivation below) computes the
    per-batch + summary rows from the accounting books.
    """

    _name = 'cost.of.cultivation.wizard'
    _description = 'Cost of Cultivation Report Wizard'

    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)

    @api.onchange('date_from', 'date_to')
    def _onchange_dates(self):
        # Keep a sane default when the user clears a field.
        if not self.date_from and self.date_to:
            self.date_from = fields.Date.add(self.date_to, months=-1, day=1)
        if not self.date_to and self.date_from:
            self.date_to = fields.Date.add(self.date_from, months=1, day=1) - timedelta(days=1)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        res['date_to'] = today.replace(day=1) - timedelta(days=1)
        res['date_from'] = res['date_to'].replace(day=1)
        return res

    def action_report_cost_of_cultivation(self):
        """Print the Cost of Cultivation report for the selected period."""
        self.ensure_one()
        report_name = 'vivafarm_report.report_cost_of_cultivation'
        return self.env['ir.actions.report']._get_report_from_name(
            report_name
        ).report_action(self)


class ReportCostOfCultivation(models.AbstractModel):
    """Data model for the Cost of Cultivation QWeb report.

    Shows the REAL full cost per kg of finished goods, which the accounting
    books split across P&L accounts (material 511100, labor 511200, overhead
    618400/613100/618500/618600, depreciation 612400). FG product
    standard_price carries material-only cost; this report adds labor +
    overhead + depreciation for management pricing/margin decisions.

    Post-close-aware: the year-end close move zeroes P&L accounts (Dr = Cr
    to Retained Earnings), so period totals are read as GROSS DEBITS from
    the account lines (the debit side is the original expense; the credit
    side is the close). Per-batch material/labor come from per-batch records
    (packed move value + LABOR-ALLOC JE), which are unaffected by the close.

    Allocation: overhead + depreciation are monthly bills, not per-batch.
    Allocate by kg produced (single-crop farm; water/fuel scale with output):
      batch_share = batch_kg / total_kg
    """

    _name = 'report.vivafarm_report.report_cost_of_cultivation'
    _description = 'Cost of Cultivation Report Data'

    @api.model
    def _gross_debit(self, acc_code, date_from, date_to):
        """Period expense = gross debits on the account (post-close-aware:
        the close move credits the P&L account, so net balance is 0)."""
        acc = self.env['account.account'].search([('code', '=', acc_code)], limit=1)
        if not acc:
            return 0.0
        lines = self.env['account.move.line'].search([
            ('account_id', '=', acc.id),
            ('parent_state', '=', 'posted'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ])
        return sum(lines.mapped('debit'))

    @api.model
    def _batch_material_cost(self, cul):
        """Exact material cost of the batch = packed move value (set by
        action_done from total_input_cost, material only)."""
        if not cul.packed_picking_id:
            return 0.0
        packed_move = cul.packed_picking_id.move_ids.filtered(
            lambda m: m.product_id == cul.packed_product_id)[:1]
        return packed_move.value if packed_move else 0.0

    @api.model
    def _batch_labor_cost(self, cul):
        """Exact labor share of the batch = LABOR-ALLOC JE (Dr 511200)."""
        je = self.env['account.move'].search([
            ('ref', '=', f'LABOR-ALLOC-{cul.id}'),
            ('state', '=', 'posted'),
        ], limit=1)
        if not je:
            return 0.0
        return sum(l.debit for l in je.line_ids if l.account_id.code == '511200')

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['cost.of.cultivation.wizard'].browse(docids)
        date_from = wizard.date_from
        date_to = wizard.date_to
        currency = self.env.company.currency_id

        # Cultivations harvested in the period
        cults = self.env['vivafarm.cultivation'].search([
            ('state', '=', 'done'),
            ('harvest_date', '>=', date_from),
            ('harvest_date', '<=', date_to),
        ], order='harvest_date, id')

        total_kg = sum(c.packed_kg for c in cults)

        material_total = self._gross_debit('511100', date_from, date_to)
        labor_total = self._gross_debit('511200', date_from, date_to)
        overhead_total = sum(
            self._gross_debit(c, date_from, date_to)
            for c in ['618400', '613100', '618500', '618600']
        )
        depr_total = self._gross_debit('612400', date_from, date_to)

        overhead_rate = overhead_total / total_kg if total_kg else 0.0
        depr_rate = depr_total / total_kg if total_kg else 0.0

        rows = []
        for cul in cults:
            kg = cul.packed_kg
            mat = self._batch_material_cost(cul)
            lab = self._batch_labor_cost(cul)
            ovh = kg * overhead_rate
            depr = kg * depr_rate
            full = mat + lab + ovh + depr
            rows.append({
                'name': cul.name,
                'crop': cul.packed_product_id.name if cul.packed_product_id else '?',
                'kg': kg,
                'material': mat,
                'labor': lab,
                'overhead': ovh,
                'depr': depr,
                'full': full,
                'per_kg': full / kg if kg else 0.0,
            })

        full_total = material_total + labor_total + overhead_total + depr_total
        full_per_kg = full_total / total_kg if total_kg else 0.0

        summary = {
            'kg': total_kg,
            'material': material_total,
            'labor': labor_total,
            'overhead': overhead_total,
            'depr': depr_total,
            'full': full_total,
            'material_per_kg': material_total / total_kg if total_kg else 0.0,
            'labor_per_kg': labor_total / total_kg if total_kg else 0.0,
            'overhead_per_kg': overhead_rate,
            'depr_per_kg': depr_rate,
            'full_per_kg': full_per_kg,
        }

        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'date_from': date_from,
            'date_to': date_to,
            'rows': rows,
            'summary': summary,
            'fmt': lambda v: format_amount(self.env, v, currency),
        }
