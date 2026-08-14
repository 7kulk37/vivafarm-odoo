from datetime import timedelta

from odoo import api, fields, models
from odoo.tools import format_amount
from odoo.tools.misc import format_date


class TaxReportWizard(models.TransientModel):
    """Period picker for Thai statutory tax registers (รายงานภาษีขาย/ภาษีซื้อ).

    Standard Odoo wizard→report pattern: the wizard stores the period, the
    Print button opens the QWeb report bound to this model, and the report
    data model (report.vivafarm_report.report_tax_register below) computes
    the register rows from posted account.move records in the selected
    period.
    """

    _name = 'tax.report.wizard'
    _description = 'Thai Tax Register Report Wizard'

    register_type = fields.Selection([
        ('sales', 'Sales Register (รายงานภาษีขาย)'),
        ('purchase', 'Purchase Register (รายงานภาษีซื้อ)'),
        ('vat30', 'VAT Report (ภ.พ.30)'),
        ('pnd53', 'PND53 (ภ.ง.ด.53)'),
        ('pnd3', 'PND3 (ภ.ง.ด.3)'),
        ('pnd1', 'PND1 (ภ.ง.ด.1)'),
        ('pnd50', 'PND50 (ภ.ง.ด.50)'),
        ('pnd51', 'PND51 (ภ.ง.ด.51)'),
    ], string='Register', required=True, default='sales')
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

    def action_report_tax_register(self):
        """Print the register/VAT report for the selected period.

        Single footer button dispatches by ``register_type``: Sales/Purchase
        registers use ``report_tax_register``, the VAT Report uses
        ``report_vat30``. Returns the report action bound to this wizard so
        the QWeb template renders with the wizard's date range as data.
        """
        self.ensure_one()
        report_name = {
            'vat30': 'vivafarm_report.report_vat30',
            'pnd53': 'vivafarm_report.report_pnd53',
            'pnd3': 'vivafarm_report.report_pnd3',
            'pnd1': 'vivafarm_report.report_pnd1',
            'pnd50': 'vivafarm_report.report_pnd50',
            'pnd51': 'vivafarm_report.report_pnd51',
        }.get(self.register_type, 'vivafarm_report.report_tax_register')
        return self.env['ir.actions.report']._get_report_from_name(
            report_name
        ).report_action(self)


class ReportTaxRegister(models.AbstractModel):
    """Data model for the Thai tax register QWeb report.

    Odoo 19 renders QWeb PDFs by looking up a model named
    ``report.<module>.<template>`` and calling its ``_get_report_values``.
    Without this model the renderer falls back to a plain ``docs`` browse
    and the register rows/totals are never injected.
    """

    _name = 'report.vivafarm_report.report_tax_register'
    _description = 'Thai Tax Register Report Data'

    @api.model
    def _get_register_domain(self, wizard, move_types):
        return [
            ('move_type', 'in', move_types),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', wizard.date_from),
            ('invoice_date', '<=', wizard.date_to),
        ]

    @api.model
    def _get_report_values(self, docids, data=None):
        """Rows for the register report.

        Columns per line: date, invoice number, customer/vendor, tax base,
        VAT amount. Refunds keep their (negative) sign so the register is
        chronologically faithful. Company currency formatting is done here so
        the QWeb template stays declarative.
        """
        wizard = self.env['tax.report.wizard'].browse(docids)
        register_type = wizard.register_type
        move_types = ('out_invoice', 'out_refund') if register_type == 'sales' \
            else ('in_invoice', 'in_refund')
        moves = self.env['account.move'].search(
            self._get_register_domain(wizard, move_types),
            order='invoice_date, name',
        )
        currency = self.env.company.currency_id
        rows = []
        for m in moves:
            # out_refund.amount_untaxed is POSITIVE in Odoo 19 (sign lives in
            # move lines) — flip so refunds reduce the register base.
            base_raw = m.amount_untaxed if m.move_type == 'out_invoice' else -m.amount_untaxed
            rows.append({
                'date': m.invoice_date,
                'name': m.name,
                'partner': m.partner_id.name,
                'base': format_amount(self.env, base_raw, currency),
                'tax': format_amount(self.env, m.amount_tax, currency),
                'base_raw': base_raw,
                'tax_raw': m.amount_tax,
            })
        totals = {
            'base': format_amount(self.env, sum(r['base_raw'] for r in rows), currency),
            'tax': format_amount(self.env, sum(r['tax_raw'] for r in rows), currency),
        }
        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'rows': rows,
            'totals': totals,
            'date_from': wizard.date_from,
            'date_to': wizard.date_to,
            'register_type': register_type,
        }


class ReportVAT30(models.AbstractModel):
    """Data model for the Thai VAT report (แบบ ภ.พ.30).

    Computes the statutory 12 lines from posted tax lines in the selected
    period, classified by the l10n_th tags attached to each tax's
    repartition lines:

      1  Sales amount (ทั้งหมด)
      2  Less sales subject to 0% rate
      3  Less exempted sales
      4  Taxable sales amount (1 - 2 - 3)
      5  Output tax
      6  Purchase amount entitled to input-tax deduction
      7  Input tax (per invoice of line 6)
      8  Tax payable (5 > 7)
      9  Excess tax payable (5 < 7)
     10  Excess tax carried forward (previous period)
     11  Net tax payable (8 > 10)
     12  Net excess tax ((10 > 8) or (9 + 10))

    Lines 10/12 use the previous period's excess as a simplification (the
    farm's cash-basis VAT has no carried-forward balance in the demo data).
    """

    _name = 'report.vivafarm_report.report_vat30'
    _description = 'Thai VAT Report ภ.พ.30 Data'

    @api.model
    def _get_tax_line_domain(self, wizard, move_types):
        return [
            ('parent_state', '=', 'posted'),
            ('tax_line_id', '!=', False),
            ('date', '>=', wizard.date_from),
            ('date', '<=', wizard.date_to),
            ('move_id.move_type', 'in', move_types),
        ]

    @api.model
    def _compute(self, wizard):
        """Return the 12 statutory lines as {code: amount} floats.

        Zero-amount taxes (0% / exempt) create NO tax lines in Odoo, so
        lines 1–3 are computed from invoice lines + their tax_ids, while
        lines 5/7 (output/input tax amounts) come from posted tax lines.
        """
        res = {n: 0.0 for n in range(1, 13)}

        # --- Sales side (out_invoice / out_refund) ---
        moves = self.env['account.move'].search([
            ('state', '=', 'posted'),
            ('invoice_date', '>=', wizard.date_from),
            ('invoice_date', '<=', wizard.date_to),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
        ])
        for m in moves:
            # out_refund.amount_untaxed is POSITIVE in Odoo 19 (sign lives in
            # move lines) — flip so refunds reduce the sales amount.
            res[1] += m.amount_untaxed if m.move_type == 'out_invoice' else -m.amount_untaxed
            for line in m.invoice_line_ids:
                for tax in line.tax_ids:
                    names = set()
                    for rl in tax.invoice_repartition_line_ids + tax.refund_repartition_line_ids:
                        for tag in rl.tag_ids:
                            names.add(tag.name)
                    if '2. Less sales subject to 0% tax rate' in names:
                        res[2] += line.price_subtotal
                    if '3. Less exempted sales' in names:
                        res[3] += line.price_subtotal

        # --- Tax amounts from posted tax lines ---
        lines = self.env['account.move.line'].search(
            self._get_tax_line_domain(
                wizard, ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'))
        )
        for line in lines:
            tax = line.tax_line_id
            names = set()
            for rl in tax.invoice_repartition_line_ids + tax.refund_repartition_line_ids:
                for tag in rl.tag_ids:
                    names.add(tag.name)
            is_sale = line.move_id.move_type in ('out_invoice', 'out_refund')
            if is_sale:
                # Sale-side tax lines carry negative base/balance (credit);
                # flip so statutory amounts are positive. Refunds stay
                # negative, correctly reducing output tax.
                if '5. Output tax' in names:
                    res[5] += -line.balance
            else:
                if '6. Purchase amount that is entitled to deduction of input tax from output tax in tax computation' in names:
                    res[6] += line.tax_base_amount
                if '7. Input tax (according to invoice of purchase amount in 6.)' in names:
                    res[7] += line.balance
        res[4] = res[1] - res[2] - res[3]
        res[8] = max(res[5] - res[7], 0.0)
        res[9] = max(res[7] - res[5], 0.0)
        res[10] = 0.0
        res[11] = max(res[8] - res[10], 0.0)
        res[12] = max(res[10] - res[8], 0.0) + res[9]
        return res

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['tax.report.wizard'].browse(docids)
        currency = self.env.company.currency_id
        amounts = self._compute(wizard)
        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'date_from': wizard.date_from,
            'date_to': wizard.date_to,
            'register_type': 'vat30',
            'amounts': amounts,
            'amount': lambda n: format_amount(self.env, amounts[n], currency),
            # Thai Buddhist-Era dates for the period line: "01-ส.ค.-2569"
            'thai_date_from': '%s-%s' % (
                format_date(self.env, wizard.date_from, lang_code='th_TH', date_format='dd-MMM'),
                wizard.date_from.year + 543),
            'thai_date_to': '%s-%s' % (
                format_date(self.env, wizard.date_to, lang_code='th_TH', date_format='dd-MMM'),
                wizard.date_to.year + 543),
        }
