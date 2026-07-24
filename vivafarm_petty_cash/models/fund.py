# -*- coding: utf-8 -*-
"""Vivafarm Petty Cash — fund and voucher models.

Custodian-based petty cash float with voucher tracking.
Posting model:
  - Top-up:    Dr 111102 Petty Cash  / Cr 111203 Bank
  - Outlay:    tracked in voucher sub-ledger, no GL post
  - Replenish: Dr expense_account  / Cr 111102 Petty Cash
               Dr 111102 Petty Cash / Cr 111203 Bank
  - Variance:  Dr 639900 Petty Cash Variance / Cr 111102 (or reverse)
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class VivafarmPettyCashFund(models.Model):
    _name = 'vivafarm.petty.cash.fund'
    _description = 'Petty Cash Fund (custodian + float ceiling)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Fund Name',
        required=True,
        help='e.g. "Manager Float", "Farm Petty Cash"',
    )
    custodian_id = fields.Many2one(
        'res.partner',
        string='Custodian',
        required=True,
        help='The person who holds the cash and is responsible for vouchers',
    )
    float_ceiling = fields.Monetary(
        string='Float Ceiling',
        required=True,
        currency_field='currency_id',
        help='Maximum cash allowed in the drawer at any time. '
             'Anything above this must be deposited to bank.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Petty Cash Journal',
        required=True,
        domain=[('type', '=', 'cash')],
    )
    account_id = fields.Many2one(
        'account.account',
        string='Petty Cash Account',
        required=True,
        help='GL account where float balance is held (e.g. 111102 Petty Cash)',
    )
    variance_account_id = fields.Many2one(
        'account.account',
        string='Variance Account',
        required=True,
        help='Over/short account for cash count discrepancies (e.g. 639900)',
    )
    max_voucher_amount = fields.Monetary(
        string='Max Voucher Amount',
        required=True,
        default=2000.0,
        currency_field='currency_id',
        help='Maximum amount per single voucher. Larger expenses must go through bank.',
    )
    receipt_required_above = fields.Monetary(
        string='Receipt Required Above',
        required=True,
        default=1000.0,
        currency_field='currency_id',
        help='Vouchers above this THB amount require an attached receipt (Thai Revenue Code §3).',
    )
    active = fields.Boolean(default=True)

    # Counts
    voucher_ids = fields.One2many(
        'vivafarm.petty.cash.voucher',
        'fund_id',
        string='Vouchers',
    )
    voucher_count = fields.Integer(
        string='Voucher Count',
        compute='_compute_voucher_count',
    )
    current_balance = fields.Monetary(
        string='Current Float Balance',
        currency_field='currency_id',
        compute='_compute_current_balance',
        help='Float ceiling minus unreconciled voucher total. '
             'This is the expected cash in the drawer.',
    )
    disbursed_total = fields.Monetary(
        string='Disbursed (Unreconciled)',
        currency_field='currency_id',
        compute='_compute_current_balance',
        help='Sum of draft + submitted vouchers not yet replenished.',
    )

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)',
         'Fund name must be unique.'),
    ]

    @api.depends('voucher_ids', 'voucher_ids.state', 'voucher_ids.amount')
    def _compute_voucher_count(self):
        for f in self:
            f.voucher_count = len(f.voucher_ids)

    @api.depends('voucher_ids.state', 'voucher_ids.amount')
    def _compute_current_balance(self):
        for f in self:
            open_vouchers = f.voucher_ids.filtered(
                lambda v: v.state in ('draft', 'submitted')
            )
            f.disbursed_total = sum(open_vouchers.mapped('amount'))
            f.current_balance = f.float_ceiling - f.disbursed_total

    @api.constrains('float_ceiling', 'max_voucher_amount', 'receipt_required_above')
    def _check_amounts(self):
        for f in self:
            if f.float_ceiling <= 0:
                raise ValidationError(_('Float ceiling must be positive.'))
            if f.max_voucher_amount <= 0:
                raise ValidationError(_('Max voucher amount must be positive.'))
            if f.receipt_required_above < 0:
                raise ValidationError(_('Receipt threshold cannot be negative.'))

    def action_view_vouchers(self):
        self.ensure_one()
        return {
            'name': _('Vouchers'),
            'type': 'ir.actions.act_window',
            'res_model': 'vivafarm.petty.cash.voucher',
            'view_mode': 'tree,form',
            'domain': [('fund_id', '=', self.id)],
            'context': {'default_fund_id': self.id},
        }


class VivafarmPettyCashVoucher(models.Model):
    _name = 'vivafarm.petty.cash.voucher'
    _description = 'Petty Cash Voucher (one cash outlay)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'

    name = fields.Char(
        string='Voucher Number',
        required=True,
        default=lambda self: _('New'),
        readonly=True,
    )
    fund_id = fields.Many2one(
        'vivafarm.petty.cash.fund',
        string='Fund',
        required=True,
        ondelete='restrict',
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
    )
    payee = fields.Char(
        string='Payee',
        required=True,
        help='Who received the cash (e.g. shop name, employee name)',
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='fund_id.currency_id',
        string='Currency',
    )
    expense_account_id = fields.Many2one(
        'account.account',
        string='Expense Account',
        required=True,
        help='GL account to charge when this voucher is replenished',
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        help='Optional project/analytic tracking',
    )
    description = fields.Text(
        string='Description',
        required=True,
        help='What the cash was for (e.g. "Bought 5 kg fertilizer")',
    )
    receipt_attached = fields.Boolean(
        string='Receipt Attached',
        help='User confirms they have a paper receipt. '
             'Mandatory above the fund receipt threshold (Thai Revenue Code §3).',
    )
    state = fields.Selection(
        [('draft', 'Draft'),
         ('submitted', 'Submitted'),
         ('reconciled', 'Reconciled'),
         ('cancelled', 'Cancelled')],
        string='Status',
        default='draft',
        tracking=True,
    )
    journal_entry_id = fields.Many2one(
        'account.move',
        string='Replenishment JE',
        readonly=True,
        help='The replenishment journal entry that consumed this voucher',
    )

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)',
         'Voucher number must be unique.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'vivafarm.petty.cash.voucher'
                ) or _('New')
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for v in self:
            if v.amount <= 0:
                raise ValidationError(_('Voucher amount must be positive.'))
            if v.amount > v.fund_id.max_voucher_amount:
                raise UserError(_(
                    'Voucher amount %s exceeds fund max %s. '
                    'Use a bank payment for larger expenses.'
                ) % (v.amount, v.fund_id.max_voucher_amount))

    @api.constrains('receipt_attached', 'amount')
    def _check_receipt(self):
        for v in self:
            threshold = v.fund_id.receipt_required_above
            if v.amount > threshold and not v.receipt_attached:
                raise ValidationError(_(
                    'Receipt required for vouchers above %s %s (Thai Revenue Code §3).'
                ) % (threshold, v.currency_id.name))

    def action_submit(self):
        for v in self:
            if v.state != 'draft':
                continue
            v.write({'state': 'submitted'})
        return True

    def action_cancel(self):
        for v in self:
            if v.state == 'reconciled':
                raise UserError(_(
                    'Cannot cancel a voucher that has already been replenished. '
                    'Reverse the replenishment JE instead.'
                ))
            v.write({'state': 'cancelled'})
        return True

    def action_draft(self):
        for v in self:
            v.write({'state': 'draft'})
        return True
