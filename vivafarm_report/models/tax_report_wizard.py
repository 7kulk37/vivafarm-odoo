from datetime import timedelta

from odoo import api, fields, models
from odoo.tools import format_amount


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
        """Print the register for the selected period (wizard footer button).

        Returns the report action bound to this wizard model so the QWeb
        template renders with the wizard's date range as the report data.
        """
        self.ensure_one()
        return self.env['ir.actions.report']._get_report_from_name(
            'vivafarm_report.report_tax_register'
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
            rows.append({
                'date': m.invoice_date,
                'name': m.name,
                'partner': m.partner_id.name,
                'base': format_amount(self.env, m.amount_untaxed, currency),
                'tax': format_amount(self.env, m.amount_tax, currency),
                'base_raw': m.amount_untaxed,
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
