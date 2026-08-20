#!/usr/bin/env python3
"""invoice_send_inv_test_2027 — RED test: Send INV button + Viva Invoice PDF in send wizard.

Asserts:
  T1  action_send_invoice_viva exists on account.move
  T2  it opens the standard send wizard with context flag viva_invoice_report
  T3  _get_default_pdf_report_id returns the Viva Invoice (ใบแจ้งหนี้) report under the flag
  T4  wizard.pdf_report_id = viva_invoice_plain when opened with the flag
  T5  without the flag, default stays standard (account.account_invoices)
  T6  Send INV button present in the form view (mirrors Send visibility)
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

# ── Setup: a posted customer invoice ──
inv = env['account.move'].search([
    ('move_type', '=', 'out_invoice'),
    ('state', '=', 'posted'),
    ('name', '!=', '/'),
], order='id desc', limit=1)
print('INV', inv.id, inv.name)

# ── T1: method exists ──
check('T1 action_send_invoice_viva exists',
      hasattr(env['account.move'], 'action_send_invoice_viva'))

# ── T2: action opens wizard with flag ──
try:
    act = inv.action_send_invoice_viva()
    check('T2 returns wizard action', act.get('res_model') == 'account.move.send.wizard',
          '(got %s)' % act.get('res_model'))
    check('T2 context has viva_invoice_report',
          act.get('context', {}).get('viva_invoice_report') is True,
          '(got %s)' % act.get('context', {}).get('viva_invoice_report'))
except Exception as e:
    check('T2 returns wizard action', False, str(e)[:120])

# ── T3: _get_default_pdf_report_id under flag ──
try:
    send = env['account.move.send']
    viva_rpt = env.ref('vivafarm_report.report_viva_invoice_plain')
    with_flag = send.with_context(viva_invoice_report=True)._get_default_pdf_report_id(inv)
    check('T3 flag returns Viva Invoice report', with_flag.id == viva_rpt.id,
          '(got %s)' % with_flag.id)
except Exception as e:
    check('T3 flag returns Viva Invoice report', False, str(e)[:120])

# ── T4: wizard pdf_report_id under flag ──
try:
    wiz = env['account.move.send.wizard'].with_context(
        viva_invoice_report=True,
        active_model='account.move',
        active_ids=inv.ids,
    ).create({'move_id': inv.id})
    check('T4 wizard pdf_report_id = Viva Invoice', wiz.pdf_report_id.id == viva_rpt.id,
          '(got %s)' % wiz.pdf_report_id.id)
    wiz.unlink()
except Exception as e:
    check('T4 wizard pdf_report_id = Viva Invoice', False, str(e)[:120])

# ── T5: without flag, default stays standard ──
try:
    std = send._get_default_pdf_report_id(inv)
    std_rpt = env.ref('account.account_invoices')
    check('T5 no-flag default is standard', std.id == std_rpt.id,
          '(got %s)' % std.id)
except Exception as e:
    check('T5 no-flag default is standard', False, str(e)[:120])

# ── T6: Send INV button in form view ──
try:
    view = env.ref('vivafarm_report.view_move_form_vivafarm_tax_invoice_button')
    arch = view.arch
    check('T6 Send INV button view exists', True)
    check('T6 button string Send INV', 'Send INV' in arch)
    check('T6 button calls action_send_invoice_viva', 'action_send_invoice_viva' in arch)
    check('T6 mirrors display_send_button', 'display_send_button' in arch)
    check('T6 highlighted', 'class="oe_highlight"' in arch)
except Exception as e:
    check('T6 Send INV button view exists', False, str(e)[:120])

# ── Summary ──
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
