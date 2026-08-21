#!/usr/bin/env python3
"""digital_flow_both_test — digital Accept & Sign for BOTH partner flows.

Standard flow partner: no invoice_template_pdf_report_id.
  - SO accept & sign  -> sale_order digital record (channel='digital')
  - Invoice accept    -> document_type='invoice'
Minimal flow partner: invoice_template_pdf_report_id = Tax invoice.
  - SO accept & sign  -> sale_order digital record (channel='digital')
  - Invoice accept    -> document_type='tax_invoice'

Checks:
  D1  Standard SO digital accept -> signed record, channel='digital'
  D2  Standard invoice digital accept -> document_type='invoice'
  D3  Minimal SO digital accept -> signed record, channel='digital'
  D4  Minimal invoice digital accept -> document_type='tax_invoice'
  D5  Verify pages: standard VALID badge, minimal VALID badge
  D6  Tax vs plain stored PDFs DIFFER (bytes not cross-shared)
  D7  No cross-contamination: each invoice's signed record has its OWN doc_type
"""
import base64
import hashlib
import json
import urllib.request
import urllib.error

from odoo import fields

PASS = 0
FAIL = 0
STS = (302, 303)

PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  PASS: %s %s' % (name, detail))
    else:
        FAIL += 1
        print('  FAIL: %s %s' % (name, detail))


def http_jsonrpc(url, payload, headers=None):
    """POST a jsonrpc payload; return parsed response or raise."""
    data = json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': payload}).encode()
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Host', 'test_sign.stg.vivafarm')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def verify_get(token):
    req = urllib.request.Request('http://127.0.0.1:8069/v/%s' % token,
                                 headers={'Host': 'test_sign.stg.vivafarm'})
    return urllib.request.urlopen(req, timeout=30).read().decode()


def get_signed(model, rid, doc_type):
    return env['viva.signed.document'].sudo().search([
        ('odoo_model', '=', model),
        ('odoo_record_id', '=', rid),
        ('document_type', '=', doc_type),
    ], limit=1)


print('=== digital_flow_both_test — digital chain: standard AND minimal ===')

env.cr.rollback()

# ── Setup ──
standard = env['res.partner'].search([('name', '=', 'DIGI Standard Partner')], limit=1)
if not standard:
    standard = env['res.partner'].create({
        'name': 'DIGI Standard Partner', 'is_company': True, 'lang': 'en_US',
        'email': 'digi-standard@example.invalid',
    })
tax_rep = env['ir.actions.report'].search([('report_name', '=', 'vivafarm_report.viva_invoice')], limit=1)
minimal = env['res.partner'].search([('name', '=', 'DIGI Minimal Partner')], limit=1)
if not minimal:
    minimal = env['res.partner'].create({
        'name': 'DIGI Minimal Partner', 'is_company': True, 'lang': 'en_US',
        'email': 'digi-minimal@example.invalid',
        'invoice_template_pdf_report_id': tax_rep.id if tax_rep else False,
    })
service = env['product.product'].search([('name', '=', 'DIGI Service Product')], limit=1)
if not service:
    service = env['product.product'].create({'name': 'DIGI Service Product', 'type': 'service', 'sale_ok': True})
    income = env['account.account'].search([('account_type', '=', 'income')], limit=1)
    service.write({'property_account_income_id': income.id})
pricelist = env['product.pricelist'].search([], limit=1)
check('setup tax report resolved', bool(tax_rep), '(id=%s)' % (tax_rep.id if tax_rep else 'n/a'))


def make_so(partner):
    so = env['sale.order'].create({
        'partner_id': partner.id, 'pricelist_id': pricelist.id,
        'order_line': [(0, 0, {
            'product_id': service.id, 'product_uom_qty': 1, 'price_unit': 50,
        })],
    })
    # The digital accept route signs a DRAFT/SENT quotation (the customer has
    # NOT accepted yet) — confirming first moves it to 'sale' and fails the
    # stock _has_to_be_signed() guard. Keep it draft (token only).
    so._portal_ensure_token()
    return so


def sign_so(so):
    """Digital portal accept & sign (SO). Returns the jsonrpc response."""
    env.cr.commit()
    url = 'http://127.0.0.1:8069/my/orders/%d/accept_viva' % so.id
    return http_jsonrpc(url, {
        'order_id': so.id, 'access_token': so.access_token,
        'name': 'Digital Guy', 'signature': base64.b64encode(PNG).decode(),
        'position': 'Manager',
    })


def make_invoice(partner):
    inv = env['account.move'].create({
        'move_type': 'out_invoice', 'partner_id': partner.id,
        'invoice_date': fields.Date.today(), 'invoice_line_ids': [(0, 0, {
            'product_id': service.id, 'quantity': 1, 'price_unit': 50,
        })],
    })
    inv.action_post()
    inv._portal_ensure_token()
    return inv


def sign_invoice(inv):
    env.cr.commit()
    url = 'http://127.0.0.1:8069/my/invoices/%d/accept_viva' % inv.id
    return http_jsonrpc(url, {
        'invoice_id': inv.id, 'access_token': inv.access_token,
        'name': 'Digital Buyer', 'signature': base64.b64encode(PNG).decode(),
        'position': 'Manager',
    })


# ── D1/D3: SO accept both flows ──
print('--- D1/D3 SO accept (standard + minimal) ---')
so_std = make_so(standard)
env.cr.commit()
resp = sign_so(so_std)
env.cr.commit()
so_std.invalidate_recordset()
rec_so_std = get_signed('sale.order', so_std.id, 'sale_order')
check('D1 standard SO accept ok', resp.get('result', {}).get('force_refresh') is True,
      '(res=%s)' % (resp.get('result', {}) if 'result' in resp else resp.get('error', {})))
check('D1 standard SO record channel=digital', bool(rec_so_std) and rec_so_std.channel == 'digital',
      '(channel=%s)' % (rec_so_std.channel if rec_so_std else 'n/a'))

so_min = make_so(minimal)
env.cr.commit()
resp = sign_so(so_min)
env.cr.commit()
rec_so_min = get_signed('sale.order', so_min.id, 'sale_order')
check('D3 minimal SO accepted', resp.get('result', {}).get('force_refresh') is True,
      '(res=%s)' % (resp.get('result', {}) if 'result' in resp else resp.get('error', {})))
check('D3 minimal SO record channel=digital', bool(rec_so_min) and rec_so_min.channel == 'digital',
      '(channel=%s)' % (rec_so_min.channel if rec_so_min else 'n/a'))

# ── D2/D4: invoice accept both flows ──
print('--- D2/D4 invoice accept (standard -> invoice, minimal -> tax_invoice) ---')
inv_std = make_invoice(standard)
env.cr.commit()
resp = sign_invoice(inv_std)
env.cr.commit()
inv_std.invalidate_recordset()
rec_inv_std = get_signed('account.move', inv_std.id, 'invoice')
check('D2 standard invoice accepted', resp.get('result', {}).get('force_refresh') is True,
      '(res=%s)' % (resp.get('result', {}) if 'result' in resp else resp.get('error', {})))
check('D2 standard invoice doc_type=invoice', bool(rec_inv_std) and rec_inv_std.document_type == 'invoice',
      '(type=%s)' % (rec_inv_std.document_type if rec_inv_std else 'n/a'))

inv_min = make_invoice(minimal)
env.cr.commit()
resp = sign_invoice(inv_min)
env.cr.commit()
inv_min.invalidate_recordset()
rec_inv_min = get_signed('account.move', inv_min.id, 'tax_invoice')
check('D4 minimal invoice accepted', resp.get('result', {}).get('force_refresh') is True,
      '(res=%s)' % (resp.get('result', {}) if 'result' in resp else resp.get('error', {})))
check('D4 minimal invoice doc_type=tax_invoice', bool(rec_inv_min) and rec_inv_min.document_type == 'tax_invoice',
      '(type=%s)' % (rec_inv_min.document_type if rec_inv_min else 'n/a'))

# ── D5: verify pages VALID ──
print('--- D5 verify pages ---')
if rec_inv_std:
    html_std = verify_get(rec_inv_std.verification_token)
    check('D5 standard verify VALID badge', 'VALID' in html_std)
    check('D5 standard verify NOT manual-upload', 'MANUAL UPLOAD' not in html_std)
if rec_inv_min:
    html_min = verify_get(rec_inv_min.verification_token)
    check('D5 minimal verify VALID badge', 'VALID' in html_min)
    check('D5 minimal verify NOT manual-upload', 'MANUAL UPLOAD' not in html_min)

# ── D6: stored PDFs differ ──
print('--- D6/D7 cross-flow integrity ---')
if rec_inv_std and rec_inv_min:
    std_bytes = base64.b64decode(rec_inv_std.signed_attachment_id.datas)
    min_bytes = base64.b64decode(rec_inv_min.signed_attachment_id.datas)
    check('D6 tax vs plain PDFs differ', std_bytes != min_bytes,
          '(std=%dB min=%dB)' % (len(std_bytes), len(min_bytes)))
check('D7 standard helper does not return minimal record',
      not (rec_inv_std and rec_inv_min and rec_inv_std.id == rec_inv_min.id))

print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back)')
