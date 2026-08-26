from odoo import fields, models, api
from odoo.exceptions import UserError


class FarmYearEndClosure(models.Model):
    _name = 'farm.year.end.closure'
    _description = 'Year-End Closure (CL-29)'
    _rec_name = 'fiscal_year'

    fiscal_year = fields.Char(
        string='Fiscal Year',
        required=True,
        default=lambda self: str(fields.Date.today().year),
        help='Fiscal year being closed (e.g. 2027)',
    )
    lock_date = fields.Date(
        string='Lock Date',
        default=lambda self: fields.Date.today(),
        help='Fiscal year lock date — after this, entries can no longer be posted to the closed year',
    )
    open_periods = fields.Integer(
        string='Open Entries in Year',
        compute='_compute_checks',
        help='Count of posted journal entries dated in the fiscal year (the "open period" check)',
    )
    unposted_invoices = fields.Integer(
        string='Unposted Invoices',
        compute='_compute_checks',
        help='Invoices dated in the fiscal year that are not yet posted',
    )
    inventory_balance = fields.Monetary(
        string='Inventory Balance (113100)',
        currency_field='currency_id',
        compute='_compute_checks',
        help='Ending inventory account balance for the fiscal year (should be 0 at closure if all FG sold)',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Closed'),
    ], string='Status', default='draft', required=True)
    notes = fields.Text(string='Notes')

    @api.depends('fiscal_year')
    def _compute_checks(self):
        for record in self:
            year = record.fiscal_year or str(fields.Date.today().year)
            date_from = f'{year}-01-01'
            date_to = f'{year}-12-31'

            # Open entries dated in the year (posted entries = the "period" is still open)
            posted = self.env['account.move'].search_count([
                ('state', '=', 'posted'),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ])
            # Unposted invoices dated in the year
            unposted = self.env['account.move'].search_count([
                ('move_type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')),
                ('state', '!=', 'posted'),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ])
            # Inventory account balance at year end (account 113100)
            inv_account = self.env['account.account'].search([
                ('account_type', '=', 'asset_current'),
                ('code_store', 'like', '%113100%'),
            ], limit=1)
            inventory_balance = 0.0
            if inv_account:
                amls = self.env['account.move.line'].search([
                    ('account_id', '=', inv_account.id),
                    ('parent_state', '=', 'posted'),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                ])
                inventory_balance = sum(l.balance for l in amls)

            record.open_periods = posted
            record.unposted_invoices = unposted
            record.inventory_balance = inventory_balance

    def action_apply_lock(self):
        """CL-29: apply the fiscal year lock on the company.

        Blocks new postings before the lock date (standard Odoo 19
        year-end closure mechanism — fiscal periods were removed in v17).
        """
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Closure for {record.fiscal_year} already applied.')
            if record.unposted_invoices:
                raise UserError(
                    f'{record.unposted_invoices} unposted invoice(s) remain in {record.fiscal_year}. '
                    'Post or cancel them before closing.'
                )
            company = record.company_id or self.env.company
            company.write({'fiscalyear_lock_date': record.lock_date})
            record.state = 'done'
        return True
