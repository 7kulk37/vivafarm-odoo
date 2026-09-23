# -*- coding: utf-8 -*-
"""Post-install hooks for the petty cash module."""


def _reclass_wage_accrual_current(env):
    """222100 Employee Benefit Obligations ships in the chart as a
    non-current liability, but accrued daily wages settle within weeks —
    a CURRENT liability (audit 2026-09-22, round-2). Idempotent: only
    touches the account if it still carries the non-current type."""
    acc = env['account.account'].search([('code', '=', '222100')], limit=1)
    if acc and acc.account_type == 'liability_non_current':
        acc.write({'account_type': 'liability_current'})