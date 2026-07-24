# -*- coding: utf-8 -*-
"""Petty cash wizards: top-up and replenishment."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict


class VivafarmPettyCashTopupWizard(models.TransientModel):
    _name = 'vivafarm.petty.cash.topup'
    _description = 'Petty Cash Top-Up'

    fund_id = fields.Many2one(
        'vivafarm.petty.cash.fund',
        string='Fund',
        required=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='fund_id.currency_id',
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Source Journal',
        required=True,
        domain=[('type', 'in', ('bank', 'cash'))],
    )

    def action_confirm(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_('Top-up amount must be positive.'))
        fund = self.fund_id
        move = self.env['account.move'].create({
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': f'PCV-TOPUP-{fund.id}-{self.date}',
            'line_ids': [
                (0, 0, {
                    'account_id': fund.account_id.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'name': f'Petty cash top-up: {fund.name}',
                }),
                (0, 0, {
                    'account_id': self.journal_id.default_account_id.id,
                    'debit': 0.0,
                    'credit': self.amount,
                    'name': f'Petty cash top-up: {fund.name}',
                }),
            ],
        })
        move.action_post()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'vivafarm.petty.cash.fund',
            'view_mode': 'form',
            'res_id': fund.id,
        }


class VivafarmPettyCashReplenishWizard(models.TransientModel):
    _name = 'vivafarm.petty.cash.replenish'
    _description = 'Petty Cash Replenishment'

    fund_id = fields.Many2one(
        'vivafarm.petty.cash.fund',
        string='Fund',
        required=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
    )
    voucher_ids = fields.Many2many(
        'vivafarm.petty.cash.voucher',
        string='Vouchers to Replenish',
        required=True,
        domain="[('fund_id', '=', fund_id), ('state', 'in', ('draft', 'submitted'))]",
    )
    counted_balance = fields.Monetary(
        string='Physical Count (optional)',
        currency_field='currency_id',
        help='If entered, the system compares to the expected balance '
             'and posts any over/short to the variance account.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='fund_id.currency_id',
    )
    total_disbursed = fields.Monetary(
        string='Total Disbursed',
        currency_field='currency_id',
        compute='_compute_totals',
    )
    expected_balance = fields.Monetary(
        string='Expected Balance',
        currency_field='currency_id',
        compute='_compute_totals',
        help='Float ceiling minus sum of selected vouchers. '
             'This is the cash the custodian should have in the drawer.',
    )
    variance = fields.Monetary(
        string='Over / (Short)',
        currency_field='currency_id',
        compute='_compute_totals',
    )

    @api.depends('voucher_ids', 'counted_balance', 'fund_id.float_ceiling')
    def _compute_totals(self):
        for w in self:
            total = sum(w.voucher_ids.mapped('amount'))
            w.total_disbursed = total
            w.expected_balance = (w.fund_id.float_ceiling or 0.0) - total
            if w.counted_balance:
                w.variance = w.counted_balance - w.expected_balance
            else:
                w.variance = 0.0

    @api.onchange('fund_id')
    def _onchange_fund(self):
        if self.fund_id:
            self.voucher_ids = self.env['vivafarm.petty.cash.voucher'].search([
                ('fund_id', '=', self.fund_id.id),
                ('state', 'in', ('draft', 'submitted')),
            ])

    def action_confirm(self):
        self.ensure_one()
        if not self.voucher_ids:
            raise UserError(_('Select at least one voucher to replenish.'))
        for v in self.voucher_ids:
            if v.state == 'cancelled':
                raise UserError(_(
                    'Voucher %s is cancelled and cannot be replenished.'
                ) % v.name)
            if v.state == 'reconciled':
                raise UserError(_(
                    'Voucher %s is already replenished.'
                ) % v.name)

        fund = self.fund_id
        bank_journal = self.env['account.journal'].search([
            ('type', '=', 'bank'),
        ], limit=1)
        if not bank_journal:
            raise UserError(_('No bank journal found. Cannot replenish.'))

        total = self.total_disbursed

        # Build JE line items:
        # 1) Per-voucher: Dr expense_account / Cr petty cash
        # 2) Top-up:     Dr petty cash / Cr bank
        # 3) Variance:   if counted_balance entered, Dr/Cr variance_account

        # Group vouchers by expense_account to merge into one line per account
        by_account = defaultdict(lambda: {'amount': 0.0, 'lines': []})
        for v in self.voucher_ids:
            by_account[v.expense_account_id.id]['amount'] += v.amount
            by_account[v.expense_account_id.id]['lines'].append(v)

        line_ids = []
        # 1) Expense lines (one per expense account)
        for account_id, info in by_account.items():
            line_ids.append((0, 0, {
                'account_id': int(account_id),
                'debit': info['amount'],
                'credit': 0.0,
                'name': ', '.join(v.name for v in info['lines']),
            }))
        # 2) Cr petty cash for the disbursements (offset to expense lines)
        line_ids.append((0, 0, {
            'account_id': fund.account_id.id,
            'debit': 0.0,
            'credit': total,
            'name': f'Petty cash disbursed: {fund.name}',
        }))
        # 3) Top-up: bring float back to ceiling, adjusted for variance.
        # Top-up = total - variance. Over reduces top-up, short increases it.
        variance_amt = self.variance
        topup_amt = total - variance_amt
        # 4) Dr petty cash for the top-up
        line_ids.append((0, 0, {
            'account_id': fund.account_id.id,
            'debit': topup_amt,
            'credit': 0.0,
            'name': f'Petty cash top-up: {fund.name}',
        }))
        # 5) Cr bank for the top-up
        line_ids.append((0, 0, {
            'account_id': bank_journal.default_account_id.id,
            'debit': 0.0,
            'credit': topup_amt,
            'name': f'Petty cash top-up: {fund.name}',
        }))
        # 6) Variance reclass: the variance is cash found/missing in the drawer.
        #    Reclassify from petty cash to the variance account.
        if variance_amt != 0:
            if variance_amt > 0:
                # Over: extra cash in drawer. Move from petty to variance (income).
                line_ids.append((0, 0, {
                    'account_id': fund.account_id.id,
                    'debit': 0.0,
                    'credit': variance_amt,
                    'name': f'Petty cash over: {fund.name}',
                }))
                line_ids.append((0, 0, {
                    'account_id': fund.variance_account_id.id,
                    'debit': variance_amt,
                    'credit': 0.0,
                    'name': f'Petty cash over: {fund.name}',
                }))
            else:
                # Short: missing cash. Move from variance to petty.
                line_ids.append((0, 0, {
                    'account_id': fund.account_id.id,
                    'debit': -variance_amt,
                    'credit': 0.0,
                    'name': f'Petty cash short: {fund.name}',
                }))
                line_ids.append((0, 0, {
                    'account_id': fund.variance_account_id.id,
                    'debit': 0.0,
                    'credit': -variance_amt,
                    'name': f'Petty cash short: {fund.name}',
                }))

        move = self.env['account.move'].create({
            'journal_id': bank_journal.id,
            'date': self.date,
            'ref': f'PCV-REPLENISH-{fund.id}-{self.date}',
            'line_ids': line_ids,
        })
        move.action_post()

        # Mark vouchers as reconciled
        for v in self.voucher_ids:
            v.write({
                'state': 'reconciled',
                'journal_entry_id': move.id,
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'vivafarm.petty.cash.fund',
            'view_mode': 'form',
            'res_id': fund.id,
        }
