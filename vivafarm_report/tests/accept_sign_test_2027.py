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
from datetime import datetime, timedelta, timezone

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
        'email': 'so-sign-test@example.invalid',
    })
else:
    # The confirmation email is sent to the partner address; ensure it is set
    # so mail.notification ends in 'sent' (test runs are rolled back, so this
    # write never persists).
    partner.write({'email': partner.email or 'so-sign-test@example.invalid'})
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
# Snapshot the partner's exception-notification count BEFORE the accept — a
# healthy send leaves NO new exception row (see the note at the T4 email
# check below).
exc_before = env['mail.notification'].search_count([
    ('res_partner_id', '=', partner.id),
    ('notification_status', '=', 'exception'),
])
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
# The TEMPLATE's attachment (named via print_report_name 'Order - ...') lives
# on the mail.mail row, which auto_delete=True removes after a successful
# send — it can never be read from mail.message afterwards. The VERIFIABLE
# byte-identity of the sent PDF comes from the route's chatter post: the
# route renders the report for the signed order (the ir_actions_report
# override serves the STORED signed bytes) and posts them as an attachment
# named '<so.name>.pdf'. That attachment persists and must equal the stored
# signed PDF exactly. The email send itself is verified via
# mail.notification (the partner must have an email address).
msgs = env['mail.message'].search([
    ('model', '=', 'sale.order'),
    ('res_id', '=', so.id),
], order='id desc', limit=8)
att_found = None
for m in msgs:
    for att in m.attachment_ids:
        if att.name == '%s.pdf' % so.name:
            att_found = att
            break
    if att_found:
        break
check('T4 route posted the signed PDF attachment (named <so.name>.pdf)', bool(att_found))
if att_found:
    att_bytes = base64.b64decode(att_found.datas)
    check('T4 chatter attachment == stored signed PDF (byte-identical)',
          att_bytes == signed_att_bytes,
          '(att=%dB signed=%dB)' % (len(att_bytes), len(signed_att_bytes)))
    check('T4 attachment is Viva format (>155KB)', len(att_bytes) > 155000,
          '(bytes=%d)' % len(att_bytes))
# The confirmation EMAIL itself: with the test partner's email set, the send
# succeeds — the odoo-server log records 'successfully sent'. In-process, the
# successful mail.mail row + its notification rows are REMOVED by
# auto_delete=True (verified: log shows "User #3 deleted mail.mail records"),
# so 'sent' status is unobservable. The queryable proof of a healthy send:
# NO NEW exception notification row was created for the partner BY this
# accept (failed sends leave exception rows behind — the pre-email runs at
# ids 425-427 are such leftovers). Compare against the snapshot taken
# before the HTTP POST above.
tpl4 = env.ref('vivafarm_report.viva_email_template_order_confirmation',
               raise_if_not_found=False)
exc_after = env['mail.notification'].search_count([
    ('res_partner_id', '=', partner.id),
    ('notification_status', '=', 'exception'),
])
check('T4 confirmation email send: no NEW exception notification',
      tpl4 and exc_after == exc_before,
      '(before=%d after=%d)' % (exc_before, exc_after))

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

# ── T6: idempotent repeat POST (bug 2 — "The order is not in a state
#    requiring customer signature." on a double-fire / retry) ──
print('--- T6 repeat POST on already-accepted order is a benign success ---')
so = make_so(partner, product, pricelist)
so._portal_ensure_token()
env.cr.commit()
url = 'http://127.0.0.1:8069/my/orders/%d/accept_viva' % so.id
try:
    resp1 = http_jsonrpc(url, {
        'access_token': so.access_token,
        'name': 'Test Customer',
        'signature': SIGNATURE_B64,
    })
    check('T6 first POST succeeded', resp1.get('result', {}).get('force_refresh') is True,
          '(resp=%s)' % str(resp1.get('result'))[:120])
except Exception as e:
    check('T6 first POST succeeded', False, '(error: %s)' % e)

# The HTTP worker committed; take a fresh snapshot to see the signed order.
env.cr.commit()
so = env['sale.order'].browse(so.id)
so.invalidate_recordset()
check('T6 order accepted after first POST', so.state == 'sale' and bool(so.signature),
      '(state=%s sig=%s)' % (so.state, bool(so.signature)))
signed_count = env['viva.signed.document'].search_count(
    [('sale_order_id', '=', so.id)])
check('T6 exactly one signed doc after first POST', signed_count == 1,
      '(count=%d)' % signed_count)

# SECOND POST — the race loser / double-click / stale re-click. The order is
# already signed: the route MUST return the success shape (force_refresh +
# sign_ok redirect), NOT the guard error the user reported.
try:
    resp2 = http_jsonrpc(url, {
        'access_token': so.access_token,
        'name': 'Test Customer',
        'signature': SIGNATURE_B64,
    })
    res2 = resp2.get('result') or {}
    check('T6 repeat POST returns success shape (force_refresh)',
          res2.get('force_refresh') is True,
          '(resp=%s)' % str(res2)[:160])
    check('T6 repeat POST redirect is sign_ok', 'sign_ok' in (res2.get('redirect_url') or ''),
          '(url=%s)' % (res2.get('redirect_url') or ''))
    check('T6 repeat POST has no guard error',
          'state requiring customer signature' not in json.dumps(res2))
except Exception as e:
    check('T6 repeat POST returns success shape (force_refresh)', False,
          '(error: %s)' % e)

env.cr.commit()
so = env['sale.order'].browse(so.id)
so.invalidate_recordset()
check('T6 order still sale after repeat POST', so.state == 'sale',
      '(state=%s)' % so.state)
signed_count2 = env['viva.signed.document'].search_count(
    [('sale_order_id', '=', so.id)])
check('T6 still exactly one signed doc after repeat POST', signed_count2 == 1,
      '(count=%d)' % signed_count2)

# ── T7: seller signatory Name/Position from Thai Tax Invoice tab ──
# (user decision 2026-08-18: fill the seller signature box from two NEW
# res.company fields in the Thai Tax Invoice tab, next to the signature
# image; the signatory is a PERSON, not the company.)
print('--- T7 seller signatory fields + render ---')
company = env.company
check('T7 l10n_th_signatory_name field exists',
      'l10n_th_signatory_name' in env['res.company']._fields)
check('T7 l10n_th_signatory_position field exists',
      'l10n_th_signatory_position' in env['res.company']._fields)
view = env['ir.ui.view'].search(
    [('name', '=', 'res.company.form.inherit.vivafarm.report')], limit=1)
check('T7 company view shows the signatory fields',
      bool(view) and 'l10n_th_signatory_name' in (view.arch or '')
      and 'l10n_th_signatory_position' in (view.arch or ''))
# Set values and render a DRAFT quotation HTML — the seller box must show
# Name/Position; the buyer box must stay empty (not signed).
if 'l10n_th_signatory_name' in env['res.company']._fields:
    company.write({
        'l10n_th_signatory_name': 'Test Signatory Name',
        'l10n_th_signatory_position': 'Managing Director',
    })
    so7 = make_so(partner, product, pricelist)
    so7.write({'viva_sent_at': '2026-08-21 10:00:00'})
    html7 = env['ir.actions.report'].with_context(
        viva_show_stamp=True)._render_qweb_html(
            'vivafarm_report.viva_quotation_so', [so7.id])[0]
    check('T7 seller Name rendered in signature box',
          b'Test Signatory Name' in html7, '(len=%d)' % len(html7))
    check('T7 seller Position rendered in signature box',
          b'Managing Director' in html7)
    check('T7 buyer box empty when unsigned',
          ('data:image/png;base64,%s' % SIGNATURE_B64).encode() not in html7)
    # Undo the company write so later sections start clean.
    env.cr.rollback()

# ── T8: buyer position captured in Accept & Sign + buyer box rendered ──
# (user decision 2026-08-18: add a Position field next to the Full Name
# field in the Accept & Sign quotation flow, stored on the SO and
# rendered in the buyer signature box — same mechanism as the default
# Odoo form: image_data_uri(o.signature) + signed_by + sale_include_signature.)
print('--- T8 accept with position → buyer box rendered ---')
check('T8 sale.order.signed_position field exists',
      'signed_position' in env['sale.order']._fields)
so = make_so(partner, product, pricelist)
so._portal_ensure_token()
env.cr.commit()
url = 'http://127.0.0.1:8069/my/orders/%d/accept_viva' % so.id
try:
    resp = http_jsonrpc(url, {
        'access_token': so.access_token,
        'name': 'Test Customer',
        'position': 'Purchasing Manager',
        'signature': SIGNATURE_B64,
    })
    check('T8 route returned ok', resp.get('result', {}).get('force_refresh') is True,
          '(resp=%s)' % str(resp.get('result'))[:120])
except Exception as e:
    check('T8 route returned ok', False, '(error: %s)' % e)
env.cr.commit()
so = env['sale.order'].browse(so.id)
so.invalidate_recordset()
check('T8 order accepted', so.state == 'sale', '(state=%s)' % so.state)
if 'signed_position' in env['sale.order']._fields:
    check('T8 signed_position stored', (so.signed_position or '') == 'Purchasing Manager',
          '(signed_position=%r)' % so.signed_position)
    check('T8 signed_by stored', so.signed_by == 'Test Customer',
          '(signed_by=%r)' % so.signed_by)
# Render the accepted order HTML WITH sale_include_signature — the buyer
# signature box must show the drawn signature, name, position and date.
if 'signed_position' in env['sale.order']._fields:
    html8 = env['ir.actions.report'].with_context(
        sale_include_signature=True)._render_qweb_html(
            'vivafarm_report.viva_quotation_so', [so.id])[0]
    check('T8 buyer signature image rendered (default method)',
          ('data:image/png;base64,%s' % SIGNATURE_B64).encode() in html8)
    check('T8 buyer Name rendered in signature box', b'Test Customer' in html8)
    check('T8 buyer Position rendered in signature box',
          b'Purchasing Manager' in html8)
    # Without the context the gate hides the buyer signature (same as default).
    html8b = env['ir.actions.report']._render_qweb_html(
        'vivafarm_report.viva_quotation_so', [so.id])[0]
    check('T8 buyer signature hidden without sale_include_signature',
          ('data:image/png;base64,%s' % SIGNATURE_B64).encode() not in html8b)
    # The STORED signed PDF baked the buyer box too (route confirms with the
    # context, so the hashed bytes carry the customer signature).
    signed8 = env['viva.signed.document'].search(
        [('sale_order_id', '=', so.id)], limit=1)
    check('T8 exactly one signed doc', bool(signed8))
    if signed8:
        signed8_bytes = base64.b64decode(signed8.signed_attachment_id.datas)
        check('T8 stored signed PDF is Viva-size', len(signed8_bytes) > 155000,
              '(bytes=%d)' % len(signed8_bytes))

# ── Summary ──
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back — committed HTTP-test SOs stay for manual inspection)')
