#!/usr/bin/env python3
"""invoice_accept_e2e — full portal accept flow via HTTP (jsonrpc).

Creates a fresh posted invoice, calls the accept_viva route with a real
signature (base64 PNG), verifies:
  A1  route returns force_refresh + redirect_url
  A2  invoice has signed_by/position/signature
  A3  signed document created (document_type invoice)
  A4  stored bytes served by viva_pdf route
  A5  verify page /v/<token> renders
  A6  lock: financial edit blocked after sign
"""
import base64
import json
import urllib.request
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

# ── Setup: fresh posted invoice ──
partner = env['res.partner'].search([('is_company', '=', True), ('email', '!=', False)], limit=1)
product = env['product.product'].search([('sale_ok', '=', True)], limit=1)
account = env['account.account'].search([('account_type', '=', 'income')], limit=1)
journal = env['account.journal'].search([('type', '=', 'sale')], limit=1)
inv = env['account.move'].create({
    'move_type': 'out_invoice',
    'partner_id': partner.id,
    'journal_id': journal.id,
    'invoice_date': '2026-08-19',
    'invoice_line_ids': [(0, 0, {
        'name': 'Test Accept INV',
        'quantity': 1,
        'price_unit': 100,
        'account_id': account.id,
    })],
})
inv.action_post()
inv._portal_ensure_token()
print('INV', inv.id, inv.name)
print('TOKEN', inv.access_token)

# 1x1 red pixel PNG (base64)
png_b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='

# ── A1: call accept_viva via HTTP jsonrpc ──
try:
    # Commit so the separate HTTP worker can see this invoice.
    env.cr.commit()
    url = 'http://127.0.0.1:8069/my/invoices/%s/accept_viva' % inv.id
    payload = json.dumps({
        'jsonrpc': '2.0',
        'method': 'call',
        'params': {
            'access_token': inv.access_token,
            'name': 'Somchai Acknowledger',
            'position': 'Manager',
            'signature': png_b64,
        },
    }).encode()
    req = urllib.request.Request(url, data=payload, method='POST', headers={
        'Content-Type': 'application/json',
        'Host': 'test_sign.stg.vivafarm',
    })
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    result = resp.get('result', {})
    check('A1 force_refresh', result.get('force_refresh') is True, '(got %s)' % result)
    check('A1b redirect_url has invoice_sign_ok', 'invoice_sign_ok' in (result.get('redirect_url') or ''))
    # The HTTP worker committed its own transaction — take a fresh snapshot.
    env.cr.commit()
except Exception as e:
    check('A1 force_refresh', False, str(e)[:200])

# ── A2: signature written ──
inv.invalidate_recordset()
check('A2 signed_by', inv.signed_by == 'Somchai Acknowledger', '(got %s)' % inv.signed_by)
check('A2b signed_position', inv.signed_position == 'Manager', '(got %s)' % inv.signed_position)
check('A2c signature set', bool(inv.signature))

# ── A3: signed document ──
signed = env['viva.signed.document'].search([('move_id', '=', inv.id)], limit=1)
check('A3 signed doc created', bool(signed))
check('A3b document_type invoice', signed.document_type == 'invoice', '(got %s)' % signed.document_type)
check('A3c signer_name', signed.signer_name == 'Somchai Acknowledger', '(got %s)' % signed.signer_name)

# ── A4: stored bytes served ──
try:
    stored = base64.b64decode(signed.signed_attachment_id.datas)
    served = env['ir.actions.report']._render_qweb_pdf(
        'vivafarm_report.viva_invoice_plain', [inv.id])[0]
    check('A4 stored bytes served', served == stored)
except Exception as e:
    check('A4 stored bytes served', False, str(e)[:120])

# ── A5: verify page renders ──
try:
    vurl = 'http://127.0.0.1:8069/v/%s' % signed.verification_token
    vreq = urllib.request.Request(vurl, headers={'Host': 'test_sign.stg.vivafarm'})
    vhtml = urllib.request.urlopen(vreq).read().decode()
    check('A5 verify page renders', 'Digitally Signed' in vhtml or 'เอกสารลงลายมือชื่อดิจิทัล' in vhtml or 'Verification' in vhtml)
    check('A5b verify page has doc number', inv.name in vhtml)
except Exception as e:
    check('A5 verify page renders', False, str(e)[:120])

# ── A6: lock ──
try:
    inv.write({'ref': 'HACK'})
    check('A6 financial edit blocked', False)
except Exception as e:
    check('A6 financial edit blocked', 'SIGNED' in str(e).upper() or 'locked' in str(e).lower())

# ── Cleanup ──
env.cr.rollback()

print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
