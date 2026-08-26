from odoo import fields, models, api


class FarmCashAccrualRecon(models.Model):
    _name = 'farm.cash.accrual.recon'
    _description = 'Cash vs Accrual Reconciliation (CL-24)'
    _rec_name = 'period'

    period = fields.Char(
        string='Period',
        default=lambda self: self._default_period(),
        help='Accounting period covered (YYYY-MM)',
    )
    cash_received = fields.Monetary(
        string='Cash Received',
        currency_field='currency_id',
        compute='_compute_recon',
        help='Sum of cash/bank account movements in the period',
    )
    accrual_revenue = fields.Monetary(
        string='Accrual Revenue',
        currency_field='currency_id',
        compute='_compute_recon',
        help='Sum of sales revenue recognized in the period',
    )
    difference = fields.Monetary(
        string='Difference',
        currency_field='currency_id',
        compute='_compute_recon',
        help='Cash received minus accrual revenue — should trend to zero',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    def _default_period(self):
        today = fields.Date.today()
        return today.strftime('%Y-%m')

    @api.depends('period')
    def _compute_recon(self):
        """CL-24: cash vs accrual reconciliation.

        cash_received  = sum of posted move lines on cash/bank accounts
                         (1111xx-1113xx) in the period
        accrual_revenue = sum of posted move lines on sales revenue
                         (411100) in the period
        difference     = cash_received - accrual_revenue
        """
        Account = self.env['account.account']
        MoveLine = self.env['account.move.line']

        cash_accounts = Account.search([
            ('account_type', 'in', ('asset_cash', 'asset_bank')),
        ])
        revenue_accounts = Account.search([
            ('account_type', '=', 'income'),
        ])

        for record in self:
            period = record.period or self._default_period()
            year, month = period.split('-')
            date_from = f'{year}-{month}-01'
            date_to = f'{year}-{month}-31'

            cash_lines = MoveLine.search([
                ('account_id', 'in', cash_accounts.ids),
                ('parent_state', '=', 'posted'),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ])
            revenue_lines = MoveLine.search([
                ('account_id', 'in', revenue_accounts.ids),
                ('parent_state', '=', 'posted'),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ])

            record.cash_received = sum(l.balance for l in cash_lines)
            record.accrual_revenue = sum(l.balance for l in revenue_lines)
            record.difference = record.cash_received - record.accrual_revenue
