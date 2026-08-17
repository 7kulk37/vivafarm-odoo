#!/usr/bin/env python3
"""accept_sign_test — end-to-end test for the "Accept & Sign quotation" button.

Run against test_sign (vivafarm_report + vivafarm_document_sign installed):

    sudo -u odoo odoo shell -d test_sign --no-http \
      --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/opt/odoo-custom-addons \
      < accept_sign_test_2027.py

WHY THIS FEATURE (bug 2, user report 2026-08-17):
  The standard portal accept (sale.controllers.portal.portal_quote_accept)
  sends the confirmation email via sale.mail_template_sale_confirmation
  (template 21), whose report_template_ids = sale.report_saleorder — the
  DEFAULT Odoo report. The email is rendered INSIDE action_confirm, i.e.
  BEFORE vivafarm_document_sign hashes the order, so the attachment is a
  fresh standard-form render. The user asked for a NEW "Accept & Sign
  quotation" button that proves the fix: confirm FIRST (hash + stored
  signed PDF created), then send the VIVA confirmation template — whose
  report_template_ids = vivafarm_report.action_report_viva_quotation_so —
  so ir_actions_report._render_qweb_pdf serves the STORED SIGNED bytes in
  the email (byte-identical to the signed document, hash block included).

Checks:
  T1  New Viva confirmation template exists, model sale.order, report =
      vivafarm_report.viva_quotation_so (NOT sale.report_saleorder)
  T2  Route /my/orders/<id>/accept_viva is registered (jsonrpc, public)
  T3  Portal order page shows the "Accept & Sign quotation" button +
      the signature modal form posts to /accept_viva
  T4  POST /accept_viva with signature -> SO state sale + signed doc +
      Viva confirmation email whose attachment is byte-identical to the
      stored signed PDF (hash block present, Viva format)
  T5  Standard routes untouched: /accept still exists; the standard
      confirmation template 21 still points at sale.report_saleorder
"""
import base64
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone

from odoo.exceptions import UserError

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


def make_so(partner, product, pricelist, qty=2, price=100):
    return env['sale.order'].create({
        'partner_id': partner.id,
        'pricelist_id': pricelist.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'product_uom_qty': qty,
            'price_unit': price,
        })],
    })


def http_jsonrpc(url, payload, headers=None):
    """POST a jsonrpc payload; return parsed response or raise."""
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
        return resp.read().decode()


def http_status(method, url, payload=None):
    """Return HTTP status code for a request (does not raise on 4xx)."""
    import http.client
    from urllib.parse import urlparse
    u = urlparse(url)
    conn = http.client.HTTPConnection(u.hostname, u.port, timeout=30)
    headers = {'Host': 'test_sign.stg.vivafarm', 'Content-Type': 'application/json'}
    body = None
    if payload is not None:
        body = json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': payload}).encode()
    conn.request(method, u.path + ('?' + u.query if u.query else ''), body=body, headers=headers)
    resp = conn.getresponse()
    status = resp.status
    resp.read()
    conn.close()
    return status


print('=== accept_sign_test — "Accept & Sign quotation" button ===')

# ── Setup: test partner/product ──
partner = env['res.partner'].search([('name', '=', 'SO Sign Test Customer')], limit=1)
if not partner:
    partner = env['res.partner'].create({
        'name': 'SO Sign Test Customer', 'is_company': True, 'lang': 'en_US',
    })
product = env['product.product'].search([('name', '=', 'SO Sign Test Product')], limit=1)
if not product:
    product = env['product.product'].create({
        'name': 'SO Sign Test Product', 'type': 'service', 'sale_ok': True,
    })
pricelist = env['product.pricelist'].search([], limit=1)

# ── T1: Viva confirmation template ──
print('--- T1 Viva order-confirmation template ---')
tpl = env.ref('vivafarm_report.viva_email_template_order_confirmation', raise_if_not_found=False)
check('T1 template exists', bool(tpl))
if tpl:
    reports = [(r.report_name, r.name) for r in tpl.report_template_ids]
    check('T1 model sale.order', tpl.model == 'sale.order', '(model=%s)' % tpl.model)
    check('T1 report is Viva quotation/SO',
          any(rn == 'vivafarm_report.viva_quotation_so' for rn, _ in reports),
          '(reports=%s)' % reports)
    check('T1 NOT standard report',
          not any(rn == 'sale.report_saleorder' for rn, _ in reports),
          '(no sale.report_saleorder)')

# ── T2: /accept_viva route registered ──
print('--- T2 route registered ---')
check('T2 /accept_viva route registered',
      http_status('GET', 'http://127.0.0.1:8069/my/orders/999999/accept_viva') != 404,
      '(not 404 = route present)')

# ── T3: portal page shows the button + modal posts to /accept_viva ──
print('--- T3 portal page button ---')
so = make_so(partner, product, pricelist)
so._portal_ensure_token()
# Commit so the separate HTTP worker can see this order.
env.cr.commit()
page = ''
try:
    page = http_get('http://127.0.0.1:8069/my/orders/%d?access_token=%s' % (so.id, so.access_token))
except Exception as e:
    print('  (portal page fetch failed: %s)' % e)
check('T3 page has Accept & Sign quotation button',
      'Accept & Sign quotation' in page, '(len=%d)' % len(page))
check('T3 modal posts to /accept_viva', '/accept_viva' in page)
check('T3 modal posts to /accept (standard)', '/accept' in page)
check('T3 Viva PDF button still present', 'View Quotation / Sale Order' in page)

# ── T4: full accept via the NEW route → signed + Viva email with signed bytes ──
print('--- T4 accept via /accept_viva → Viva email with signed PDF ---')
so = make_so(partner, product, pricelist)
so._portal_ensure_token()
# Commit so the separate HTTP worker can see this order.
env.cr.commit()
url = 'http://127.0.0.1:8069/my/orders/%d/accept_viva' % so.id
try:
    resp = http_jsonrpc(url, {
        'access_token': so.access_token,
        'name': 'Test Customer',
        'signature': SIGNATURE_B64,
    })
    check('T4 route returned ok', resp.get('result', {}).get('force_refresh') is True,
          '(resp=%s)' % str(resp.get('result'))[:120])
except Exception as e:
    check('T4 route returned ok', False, '(error: %s)' % e)

# The HTTP worker committed its own transaction. The test session's
# REPEATABLE READ snapshot predates that commit, so commit here to take a
# fresh snapshot that sees the worker's changes (the SO itself is already
# committed from before the HTTP call).
env.cr.commit()
so = env['sale.order'].browse(so.id)
so.invalidate_recordset()
check('T4 state sale', so.state == 'sale', '(state=%s)' % so.state)
signed = env['viva.signed.document'].search([('sale_order_id', '=', so.id)], limit=1)
check('T4 signed doc created', bool(signed))
signed_att_bytes = b''
if signed:
    signed_att_bytes = base64.b64decode(signed.signed_attachment_id.datas)
    check('T4 signed attachment is Viva-size', len(signed_att_bytes) > 155000,
          '(bytes=%d — Viva format ~160KB)' % len(signed_att_bytes))
    check('T4 hash block in signed render',
          b'Digitally Signed Document' in env['ir.actions.report']._render_qweb_html(
              'vivafarm_report.viva_quotation_so', [so.id])[0])

# The Viva confirmation email that the route sent. Odoo 19 routes outbound
# mail through mail.message + mail.notification (mail.mail stays empty).
msgs = env['mail.message'].search([
    ('model', '=', 'sale.order'),
    ('res_id', '=', so.id),
], order='id desc', limit=8)
att_found = None
for m in msgs:
    for att in m.attachment_ids:
        if att.name.startswith('Order - ') and att.name.endswith('.pdf'):
            att_found = att
            break
    if att_found:
        break
check('T4 confirmation email with Order pdf attachment', bool(att_found))
if att_found:
    att_bytes = base64.b64decode(att_found.datas)
    check('T4 email attachment == stored signed PDF (byte-identical)',
          att_bytes == signed_att_bytes,
          '(att=%dB signed=%dB)' % (len(att_bytes), len(signed_att_bytes)))
    check('T4 email attachment is Viva format (>155KB)', len(att_bytes) > 155000,
          '(bytes=%d)' % len(att_bytes))

# ── T5: standard route + template untouched ──
print('--- T5 standard flow untouched ---')
std_tpl = env.ref('sale.mail_template_sale_confirmation')
std_reports = [(r.report_name, r.name) for r in std_tpl.report_template_ids]
check('T5 standard template 21 still standard report',
      any(rn == 'sale.report_saleorder' for rn, _ in std_reports),
      '(reports=%s)' % std_reports)
check('T5 standard /accept route still registered',
      http_status('POST', 'http://127.0.0.1:8069/my/orders/999999/accept',
                  {'access_token': 'x', 'name': 'x', 'signature': 'x'}) != 404,
      '(not 404 = route present)')

# ── Summary ──
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back — committed HTTP-test SOs stay for manual inspection)')
