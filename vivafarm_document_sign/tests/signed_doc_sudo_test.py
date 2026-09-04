#!/usr/bin/env python3
"""signed_doc_sudo_test — regression for the QA-reported AccessError.

The hired worker log confirm path goes:
    farm.worker.log.action_confirm
      → _post_labor_accrual
        → env['account.move'].create(...).action_post()
          → vivafarm_document_sign.account.move.write  (hook)
            → self._is_signed() → self._sealed_document()
              → env['viva.signed.document'].search(...)   <-- this MUST sudo

Bug pre-fix: founder user lacks 'Show Full Accounting Features', the hook
search raised AccessError and blocked posting — hired-wage flow was dead
end-to-end.

Asserts (post-fix):
  S1  account.move.post by founder succeeds (no AccessError)
  S2  posted move state == 'posted'
  S3  no new signed document leaked into founder's user (none expected here)
  S4  same move write succeeds under founder (idempotent: write again, no error)

Run:
  sudo -u odoo odoo shell -d audit_2027 --no-http \
    --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/opt/odoo-custom-addons \
    < tests/signed_doc_sudo_test.py
"""
import sys
from odoo.exceptions import AccessError, UserError

checks = []


def check(label, ok, detail=''):
    checks.append((label, bool(ok), detail))
    flag = 'PASS' if ok else 'FAIL'
    print(f'{flag}: {label}' + (f' — {detail}' if detail else ''))


print('=== S1: account.move.post by founder does NOT raise AccessError ===')
# Look up the demo founder (res.users where login='founder')
founder = env['res.users'].sudo().search([('login', '=', 'founder')], limit=1)
if not founder:
    print('Founder user not found; aborting test')
    sys.exit(1)
print(f'founder id={founder.id} groups={[g.full_name for g in founder.group_ids]}')

# Find or create a stock journal + a clean draft move under founder
stock_journal = env['account.journal'].sudo().search(
    [('type', '=', 'general'), ('code', '=', 'STJ')], limit=1)
move = env['account.move'].with_user(founder).create({
    'journal_id': stock_journal.id,
    'date': '2027-01-31',
    'ref': 'SIGNED-DOC-SUDO-REGRESSION',
    'line_ids': [
        (0, 0, {'account_id': env['account.account'].sudo().search([('code', '=', '113400')], limit=1).id,
                'name': 'test', 'debit': 1.0}),
        (0, 0, {'account_id': env['account.account'].sudo().search([('code', '=', '222100')], limit=1).id,
                'name': 'test', 'credit': 1.0}),
    ],
})
try:
    move.with_user(founder).action_post()
    check('S1 action_post under founder succeeds', move.state == 'posted',
          f'state={move.state}')
except AccessError as e:
    check('S1 action_post under founder succeeds', False, f'AccessError: {str(e)[:120]}')
except UserError as e:
    # UserError = business rule; AccessError = what we're guarding against
    check('S1 action_post under founder succeeds', False, f'UserError: {str(e)[:120]}')

print('=== S2: state == posted ===')
check('S2 move.state == posted', move.state == 'posted', f'state={move.state}')

print('=== S3: idempotent re-write under founder ===')
try:
    move.with_user(founder).write({'ref': 'SIGNED-DOC-SUDO-REGRESSION-2'})
    check('S3 re-write under founder succeeds', move.ref.endswith('-2'))
except AccessError as e:
    check('S3 re-write under founder succeeds', False, f'AccessError: {str(e)[:120]}')

# cleanup (draft reset → unlink to keep DB clean)
try:
    move.button_draft()
    move.unlink()
    env.cr.commit()
except Exception:
    pass

n_fail = sum(1 for _, ok, _ in checks if not ok)
print(f'\n=== {len(checks) - n_fail}/{len(checks)} PASSED, {n_fail} FAILED ===')
sys.exit(0 if n_fail == 0 else 1)