#!/usr/bin/env python3
"""invoice_sign_fields_test_2027 — RED test: account.move signature fields.

Asserts:
  F1  signed_by Char field exists
  F2  signed_on Datetime field exists
  F3  signed_position Char field exists
  F4  signature Image field exists (attachment=True)
  F5  fields writable on a posted invoice
  F6  fields readable back
"""
PASS = 0
FAIL = 0

def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  PASS: %s' % name)
    else:
        FAIL += 1
        print('  FAIL: %s %s' % (name, detail))

# ── F1-F4: fields exist ──
fields_map = env['account.move']._fields
check('F1 signed_by Char', 'signed_by' in fields_map and fields_map['signed_by'].type == 'char',
      '(type=%s)' % fields_map.get('signed_by', {}).type if 'signed_by' in fields_map else '')
check('F2 signed_on Datetime', 'signed_on' in fields_map and fields_map['signed_on'].type == 'datetime',
      '(type=%s)' % fields_map.get('signed_on', {}).type if 'signed_on' in fields_map else '')
check('F3 signed_position Char', 'signed_position' in fields_map and fields_map['signed_position'].type == 'char',
      '(type=%s)' % fields_map.get('signed_position', {}).type if 'signed_position' in fields_map else '')
check('F4 signature Image', 'signature' in fields_map and fields_map['signature'].type == 'binary',
      '(type=%s)' % fields_map.get('signature', {}).type if 'signature' in fields_map else '')

# ── F5-F6: writable + readable on a posted invoice ──
inv = env['account.move'].search([
    ('move_type', '=', 'out_invoice'),
    ('state', '=', 'posted'),
    ('name', '!=', '/'),
], order='id desc', limit=1)
print('INV', inv.id, inv.name)
try:
    inv.write({
        'signed_by': 'Test Signer',
        'signed_position': 'Manager',
        'signed_on': '2026-08-19 10:00:00',
    })
    inv.invalidate_recordset()
    check('F5 fields writable', True)
    check('F6a signed_by readable', inv.signed_by == 'Test Signer', '(got %s)' % inv.signed_by)
    check('F6b signed_position readable', inv.signed_position == 'Manager', '(got %s)' % inv.signed_position)
    check('F6c signed_on readable', inv.signed_on is not False, '(got %s)' % inv.signed_on)
except Exception as e:
    check('F5 fields writable', False, str(e)[:120])

# ── Summary ──
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
