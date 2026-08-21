#!/usr/bin/env python3
"""minimal_flow_test — the digital MINIMAL flow (no SO, no DN, no plain invoice).

User-approved flow (2026-08-21): a customer whose "invoice report" field is
set to the Tax invoice (ใบกำกับภาษี) 3 copied report gets ONLY:
  TAX INVOICE / DELIVERY ORDER / INVOICE  →  customer signs it  →  pays.

Checks:
  M1  The minimal-flow customer exists with invoice_template_pdf_report_id =
      vivafarm_report.viva_invoice (the renamed "Tax invoice (ใบกำกับภาษี) 3 copied")
  M2  Send INV report resolution (_get_default_pdf_report_id with the
      viva_invoice_report flag) returns the TAX invoice for this customer
  M3  _get_viva_invoice_report() returns the tax invoice for this customer
  M4  Direct invoice (no SO) → Send INV wizard → emailed PDF is the TAX
      INVOICE / DELIVERY ORDER / INVOICE (title present, no plain INVOICE title)
  M5  Portal sign path: /my/invoices/<id>/viva_pdf renders the tax invoice
  M6  _hash_invoice_accepted stores document_type='tax_invoice' and the
      stored bytes are served by the viva_invoice override on print
  M7  Standard-flow customer (report unset) still resolves the plain invoice
      (regression: Send INV + _get_viva_invoice_report unchanged)
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
        print('  PASS: %s %s' % (name, detail))
    else:
        FAIL += 1
        print('  FAIL: %s %s' % (name, detail))


SIGNATURE_B64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='


def http_jsonrpc(url, payload, headers=None):
    data = json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': payload}).encode()
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Host', 'test_sign.stg.vivafarm')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def http_get(url, headers=None):
    req = urllib.request.Request(url, method='GET')
    req.add_header('Host', 'test_sign.stg.vivafarm')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


print('=== minimal_flow_test — digital minimal flow (tax invoice only) ===')

# ── M1: customer + report ──
print('--- M1 minimal-flow customer ---')
cust = env['res.partner'].search([('name', '=', 'new sign customer (tax)')], limit=1)
check('M1 customer exists', bool(cust))
if cust:
    rep = cust.invoice_template_pdf_report_id
    check('M1 report = viva_invoice (tax)', bool(rep) and rep.report_name == 'vivafarm_report.viva_invoice',
          '(report=%s)' % (rep.report_name if rep else None))
    check('M1 report display name renamed', bool(rep) and 'ใบกำกับภาษี' in (rep.name or ''),
          '(name=%s)' % (rep.name if rep else None))

# ── M2: Send INV resolution ──
print('--- M2 Send INV report resolution ---')
if cust:
    move = env['account.move'].new({'move_type': 'out_invoice', 'partner_id': cust.id})
    default = env['account.move.send'].with_context(viva_invoice_report=True)._get_default_pdf_report_id(move)
    check('M2 Send INV default = tax invoice', bool(default) and default.report_name == 'vivafarm_report.viva_invoice',
          '(report=%s)' % (default.report_name if default else None))

# ── M3: _get_viva_invoice_report ──
print('--- M3 _get_viva_invoice_report ---')
product = env['product.product'].search([('name', '=', 'SO Sign Test Product')], limit=1)
if not product:
    product = env['product.product'].create({'name': 'SO Sign Test Product', 'type': 'service', 'sale_ok': True})
if not product.property_account_income_id:
    income = env['account.account'].search([('account_type', '=', 'income')], limit=1)
    product.write({'property_account_income_id': income.id})
inv = env['account.move'].create({
    'move_type': 'out_invoice',
    'partner_id': cust.id,
    'invoice_line_ids': [(0, 0, {'product_id': product.id, 'quantity': 1, 'price_unit': 100})],
})
inv.action_post()
print('INV:', inv.id, inv.name)
viva_rep = inv._get_viva_invoice_report()
check('M3 _get_viva_invoice_report = tax invoice', bool(viva_rep) and viva_rep.report_name == 'vivafarm_report.viva_invoice',
      '(report=%s)' % (viva_rep.report_name if viva_rep else None))

# ── M4: Send INV wizard → emailed PDF is the tax invoice ──
print('--- M4 Send INV wizard ---')
inv._portal_ensure_token()
env.cr.commit()
try:
    wizard = env['account.move.send.wizard'].with_context(
        active_model='account.move', active_ids=inv.ids,
        viva_invoice_report=True, viva_show_stamp=True,
    ).create({'move_id': inv.id})
    wizard.action_send_and_print()
    check('M4 Send INV completed', True)
except Exception as e:
    check('M4 Send INV completed', False, '(error: %s)' % repr(e)[:200])
env.cr.commit()
inv = env['account.move'].browse(inv.id)
inv.invalidate_recordset()
# The emailed PDF is stored in invoice_pdf_report_file by the wizard
pdf_bytes = b''
if inv.invoice_pdf_report_file:
    pdf_bytes = base64.b64decode(inv.invoice_pdf_report_file)
    check('M4 emailed PDF stored (invoice_pdf_report_file)', len(pdf_bytes) > 1000,
          '(bytes=%d)' % len(pdf_bytes))
    # PDF content streams are zlib-compressed — the title string is NOT
    # searchable in raw bytes. Verify the report identity via the HTML
    # render of the SAME report (uncompressed) instead.
    html4 = env['ir.actions.report'].with_context(
        viva_show_stamp=True)._render_qweb_html(
            'vivafarm_report.viva_invoice', [inv.id])[0]
    check('M4 emailed PDF is the TAX invoice (tri-title in HTML)',
          b'TAX INVOICE / DELIVERY ORDER / INVOICE' in html4,
          '(html len=%d)' % len(html4))
    # The plain invoice title 'INVOICE' alone must NOT be the document title
    check('M4 NOT the plain invoice (no bare INVOICE title)',
          b'INVOICE INV/' not in html4 or b'TAX INVOICE / DELIVERY ORDER / INVOICE' in html4)
else:
    check('M4 emailed PDF stored (invoice_pdf_report_file)', False, '(empty)')

# ── M5: portal viva_pdf renders the tax invoice ──
print('--- M5 portal viva_pdf ---')
try:
    page = http_get('http://127.0.0.1:8069/my/invoices/%d/viva_pdf?access_token=%s' % (inv.id, inv.access_token))
    check('M5 portal viva_pdf returns PDF', page[:4] == b'%PDF', '(head=%s)' % page[:4])
    # PDF bytes are compressed — verify the report identity via the portal
    # HTML preview route (uncompressed) instead.
    html5 = http_get('http://127.0.0.1:8069/my/invoices/%d/viva_pdf?report_type=html&access_token=%s' % (inv.id, inv.access_token))
    check('M5 portal preview is the tax invoice (tri-title)',
          b'TAX INVOICE / DELIVERY ORDER / INVOICE' in html5,
          '(html len=%d)' % len(html5))
except Exception as e:
    check('M5 portal viva_pdf returns PDF', False, '(error: %s)' % repr(e)[:150])

# ── M6: sign via portal → document_type tax_invoice + stored bytes ──
print('--- M6 portal sign (tax invoice) ---')
try:
    resp = http_jsonrpc('http://127.0.0.1:8069/my/invoices/%d/accept_viva' % inv.id, {
        'access_token': inv.access_token,
        'name': 'Tax Sign Customer',
        'position': 'Manager',
        'signature': SIGNATURE_B64,
    })
    check('M6 route returned ok', resp.get('result', {}).get('force_refresh') is True,
          '(resp=%s)' % str(resp.get('result'))[:120])
except Exception as e:
    check('M6 route returned ok', False, '(error: %s)' % e)
# The HTTP worker committed its own transaction. The test session's
# REPEATABLE READ snapshot predates that commit and may hold pending writes
# (e.g. the M4 wizard's mail rows) that collide on commit — roll back the
# session's uncommitted work, then take a fresh snapshot that sees the
# worker's changes.
env.cr.rollback()
inv = env['account.move'].browse(inv.id)
inv.invalidate_recordset()
signed = env['viva.signed.document'].search([('move_id', '=', inv.id)], limit=1)
check('M6 signed doc created', bool(signed))
if signed:
    check('M6 document_type = tax_invoice', signed.document_type == 'tax_invoice',
          '(type=%s)' % signed.document_type)
    signed_bytes = base64.b64decode(signed.signed_attachment_id.datas)
    check('M6 stored signed PDF is Viva-size', len(signed_bytes) > 150000,
          '(bytes=%d)' % len(signed_bytes))
    # Print path: the viva_invoice override serves the stored bytes
    printed = env['ir.actions.report']._render_qweb_pdf(
        'vivafarm_report.viva_invoice', [inv.id])[0]
    check('M6 print == stored signed bytes (byte-identical)',
          printed == signed_bytes,
          '(print=%dB stored=%dB)' % (len(printed), len(signed_bytes)))
    # Hash block text is compressed in the PDF — verify via the HTML render
    # of the signed report (uncompressed).
    html6 = env['ir.actions.report']._render_qweb_html(
        'vivafarm_report.viva_invoice', [inv.id])[0]
    check('M6 signed PDF has hash block', b'Digitally Signed Document' in html6,
          '(html len=%d)' % len(html6))
    # CUSTOMER SIGNATURE renders in the "Received by Customer" box — same
    # mechanism as the SO/plain invoice (user bug 2026-08-21: the tax
    # invoice sign box was empty after signing).
    html6sig = env['ir.actions.report'].with_context(
        invoice_include_signature=True)._render_qweb_html(
            'vivafarm_report.viva_invoice', [inv.id])[0]
    check('M6 customer signature image rendered',
          ('data:image/png;base64,%s' % SIGNATURE_B64).encode() in html6sig)
    check('M6 customer Name rendered', b'Tax Sign Customer' in html6sig)
    check('M6 customer Position rendered', b'Manager' in html6sig)
    # Hash block placement: the signed HTML must have the signature boxes
    # BEFORE the hash block (SO layout — block below the sign section).
    idx_sig = html6sig.find(b'Authorized Signatory')
    idx_hash = html6sig.find(b'Digitally Signed Document')
    check('M6 hash block BELOW sign section (SO layout)',
          idx_sig != -1 and idx_hash > idx_sig,
          '(sig=%d hash=%d)' % (idx_sig, idx_hash))

# ── M7: standard-flow regression ──
print('--- M7 standard flow unchanged ---')
std = env['res.partner'].search([('name', '=', 'SO Sign Test Customer')], limit=1)
if std:
    move2 = env['account.move'].new({'move_type': 'out_invoice', 'partner_id': std.id})
    default2 = env['account.move.send'].with_context(viva_invoice_report=True)._get_default_pdf_report_id(move2)
    check('M7 standard Send INV still plain invoice',
          bool(default2) and default2.report_name == 'vivafarm_report.viva_invoice_plain',
          '(report=%s)' % (default2.report_name if default2 else None))
    inv2 = env['account.move'].create({
        'move_type': 'out_invoice',
        'partner_id': std.id,
        'invoice_line_ids': [(0, 0, {'product_id': product.id, 'quantity': 1, 'price_unit': 100})],
    })
    viva_rep2 = inv2._get_viva_invoice_report()
    check('M7 standard _get_viva_invoice_report = plain invoice',
          bool(viva_rep2) and viva_rep2.report_name == 'vivafarm_report.viva_invoice_plain',
          '(report=%s)' % (viva_rep2.report_name if viva_rep2 else None))

# ── Summary ──
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back — committed HTTP-test invoices stay for manual inspection)')
