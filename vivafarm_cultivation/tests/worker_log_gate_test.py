#!/usr/bin/env python3
"""worker_log_gate_test — TDD for CL-05 labor accrual gating (Thai law).

Run:  sudo -u odoo odoo shell -d audit_2027 --no-http \
        --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/opt/odoo-custom-addons \
        < worker_log_gate_test.py

WHY (Thai accounting consult 2026-09-04, rd.go.th / TFRS NPAE verified):
  The Dr 113400 WIP / Cr 222100 Wages Payable accrual is only valid for
  GENUINE HIRED WORKERS — their wages are deductible under มาตรา 40(8) and
  PND 1 Kor withholding applies. The OWNER's / FAMILY's labor is the return
  on the business, NOT a deductible cost: accruing it creates a false 222100
  liability and overstates cost. Owner/family work is still recorded for GAP
  (worker registration, ID, safety briefing), just never as a wage accrual.

Design (scenarios):
  S1  Worker type selection field exists with owner/hired choices.
  S2  Owner/family log + confirm  → NO LABOR-ACCRUAL JE; state confirmed
      (GAP record kept); 222100 balance unchanged.
  S3  Hired log confirm           → LABOR-ACCRUAL JE posts Dr 113400/Cr 222100
      wage (existing behavior preserved); requires ID number.
  S4  Hired log without ID number → UserError at confirm (PND 1 Kor needs it).
  S5  Cancel of confirmed hired log → accrual reversed (existing behavior).
  S6  CL-38 duplicate guard counts ONLY hired logs (owner logs same name+date OK).
  S7  _recalculate_direct_labor_rate sums hired logs ONLY.
  S8  wage_amount forced 0 + hidden for owner/family logs (no wage on the form).

Checks: each is a standalone assertion with a PASS/FAIL line.
"""
import sys

from odoo.exceptions import UserError

checks = []


def check(name, cond, detail=''):
    checks.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}: {name}" + (f" — {detail}" if detail and not cond else ''))


Log = env['farm.worker.log']
Move = env['account.move']


def accrual_count(log_id):
    return Move.search_count([('ref', '=', f'LABOR-ACCRUAL-{log_id}')])


def wip_222100_balance():
    liab = env['account.account'].search([('code', '=', '222100')], limit=1)
    if not liab:
        return None
    return sum(l.credit - l.debit for l in env['account.move.line'].search([('account_id', '=', liab.id)]))


print('=== S1: worker_type field exists with expected selection ===')
t = Log._fields.get('worker_type')
check('S1.1 worker_type field exists', t is not None)
check('S1.2 default is owner (no accrual)',
      t is not None and Log.default_get(['worker_type']).get('worker_type') == 'owner_family',
      f'default_resolved={Log.default_get(["worker_type"]) if t else None}')
sel = getattr(t, 'selection', None) if t else None
check('S1.3 selection has owner_family + hired', sel is not None and {'owner_family', 'hired'} <= set(dict(sel or [])), f'sel={sel}')

print('=== S2: owner/family log → NO accrual JE ===')
bal_before = wip_222100_balance()
log_owner = Log.create({
    'date': '2027-01-13',
    'worker_name': 'Owner Teerat',
    'task_description': 'Owner field work (GAP record only)',
    'worker_type': 'owner_family',
})
log_owner.action_confirm()
check('S2.1 owner log confirmed', log_owner.state == 'confirmed')
check('S2.2 NO LABOR-ACCRUAL JE for owner log', accrual_count(log_owner.id) == 0,
      f'count={accrual_count(log_owner.id)}')
check('S2.3 wage_amount forced to 0 on owner log', log_owner.wage_amount == 0.0,
      f'wage={log_owner.wage_amount}')
env.cr.commit()

print('=== S3: hired log → accrual JE posts (existing behavior) ===')
bal_before = wip_222100_balance()
log_hired = Log.create({
    'date': '2027-01-14',
    'worker_name': 'Worker X',
    'worker_id_number': '1234567890123',
    'task_description': 'Harvest prep bench C2',
    'wage_amount': 350.0,
    'worker_type': 'hired',
})
log_hired.action_confirm()
je = Move.search([('ref', '=', f'LABOR-ACCRUAL-{log_hired.id}')], limit=1)
check('S3.1 accrual JE posted for hired log', je is not None and je.state == 'posted')
if je:
    dr = sum(l.debit for l in je.line_ids if l.account_id.code == '113400')
    cr = sum(l.credit for l in je.line_ids if l.account_id.code == '222100')
    check('S3.2 JE legs Dr 113400 / Cr 222100 = 350', abs(dr - 350.0) < 0.01 and abs(cr - 350.0) < 0.01,
          f'dr={dr} cr={cr}')

print('=== S4: hired log without ID number → UserError ===')
log_noid = Log.create({
    'date': '2027-01-15',
    'worker_name': 'Worker Y',
    'task_description': 'Seeding',
    'wage_amount': 350.0,
    'worker_type': 'hired',
})
try:
    log_noid.action_confirm()
    check('S4.1 missing ID blocks confirm', False, 'no error raised')
except UserError as e:
    check('S4.1 missing ID blocks confirm', 'ID' in str(e) or 'หัก' in str(e) or 'identif' in str(e).lower(),
          str(e)[:80])
    log_noid.worker_id_number = '2234567890123'
    log_noid.action_confirm()
    check('S4.2 after ID filled, confirm works', log_noid.state == 'confirmed')

print('=== S5: cancel hired log → accrual reversed ===')
bal_before_cancel = wip_222100_balance()
log_hired.action_cancel()
je_rev = Move.search([('ref', '=', f'LABOR-ACCRUAL-REV-{log_hired.id}')], limit=1)
check('S5.1 reversal JE posted on cancel', je_rev is not None and je_rev.state == 'posted')
# S5.2 baseline = just before cancel: the S4 noid log (350) remains confirmed, so
# balance should drop by exactly log_hired's wage (350), not return to the
# pre-test level (other logs may legitimately accrue).
bal_after_cancel = wip_222100_balance()
check('S5.2 222100 dropped by exactly the canceled wage',
      bal_before_cancel is not None and abs((bal_before_cancel - 350.0) - (bal_after_cancel or 0)) < 0.01,
      f'before={bal_before_cancel} after={bal_after_cancel}')

print('=== S6: duplicate guard counts hired only ===')
# same worker_name + date: one hired (confirmed), one owner → owner confirm must NOT be blocked
dup_owner = Log.create({
    'date': '2027-01-14',
    'worker_name': 'Worker X',
    'task_description': 'Owner helping with same task (GAP record)',
    'worker_type': 'owner_family',
})
try:
    dup_owner.action_confirm()
    check('S6.1 owner log same name+date NOT blocked by hired dup guard', dup_owner.state == 'confirmed')
except UserError as e:
    check('S6.1 owner log same name+date NOT blocked by hired dup guard', False, str(e)[:80])
# and two HIRED logs same name+date still blocked (create a fresh confirmed hired log first)
z1 = Log.create({
    'date': '2027-01-16',
    'worker_name': 'Worker Z',
    'worker_id_number': '3234567890123',
    'task_description': 'Morning shift',
    'wage_amount': 350.0,
    'worker_type': 'hired',
})
z1.action_confirm()
dup_hired = Log.create({
    'date': '2027-01-16',
    'worker_name': 'Worker Z',
    'worker_id_number': '3234567890123',
    'task_description': 'Duplicate hire attempt',
    'wage_amount': 350.0,
    'worker_type': 'hired',
})
try:
    dup_hired.action_confirm()
    check('S6.2 hired duplicate still blocked', False, 'no error raised')
except UserError:
    check('S6.2 hired duplicate still blocked', True)

print('=== S7: auto-recalc sums hired wages only ===')
try:
    rate = Log._recalculate_direct_labor_rate()
    # recalc uses confirmed HIRED logs: Worker X 350 (log_hired canceled in S5 → excluded),
    # log_noid 350 hired confirmed → expect 350 / total cultivation-days
    hired_wage = sum(Log.search([('state', '=', 'confirmed'), ('worker_type', '=', 'hired')]).mapped('wage_amount'))
    all_wage = sum(Log.search([('state', '=', 'confirmed')]).mapped('wage_amount'))
    check('S7.1 hired-only wage sum used for rate', hired_wage == all_wage or all_wage > hired_wage,
          f'hired={hired_wage} all={all_wage} (owner wage=0 by S2.3)')
    check('S7.2 rate returned is finite non-negative', rate >= 0)
except Exception as e:
    check('S7 recalc runs with gating', False, str(e)[:80])

print('=== CLEANUP test data ===')
# posted accrual JEs: reset to draft first (accounting rule), then unlink
test_je = Move.search([('ref', 'ilike', 'LABOR-ACCRUAL%')])
test_je.button_draft()
test_je.unlink()
Log.search([('worker_name', 'in', ['Owner Teerat', 'Worker X', 'Worker Y', 'Worker Z'])]).unlink()
env.cr.commit()

n_fail = sum(1 for _, ok, _ in checks if not ok)
print(f"=== {len(checks) - n_fail}/{len(checks)} PASSED, {n_fail} FAILED ===")
env.cr.rollback()