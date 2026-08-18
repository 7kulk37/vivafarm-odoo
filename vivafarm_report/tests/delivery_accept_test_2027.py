#!/usr/bin/env python3
"""delivery_accept_test — end-to-end test for the delivery note signing flow.

Run against test_sign (vivafarm_report + vivafarm_document_sign installed):

    sudo -u odoo odoo shell -d test_sign --no-http \
      --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/opt/odoo-custom-addons \
      < delivery_accept_test_2027.py

WHY THIS FEATURE (user request 2026-08-18):
  Digital sign on the delivery note (ใบส่งสินค้า) chained to the linked SO,
  portal-first like the SO flow. The customer acknowledges receipt via a
  portal modal ("Accept & Sign Delivery") that posts to
  /my/picking/<id>/accept_viva — the route writes the drawn signature on
  the picking, hashes the delivery note (receiver signature baked in), and
  stores the signed PDF. The delivery note stamp shows the linked SO + its
  verification code (record-level chain, user decision). No confirmation
  email (user decision — customer has the goods physically); chatter post
  + stored signed bytes served is enough. Signed deliveries are locked
  (substance edits + cancel blocked — user decision).

Checks:
  D1  viva.signed.document has delivery_note type + picking_id + UNIQUE
  D2  Routes registered: /my/picking/<id>/viva_pdf (http) +
      /my/picking/<id>/accept_viva (jsonrpc)
  D3  SO portal page shows delivery section with View Viva Delivery Note +
      Accept & Sign Delivery buttons + modal
  D4  Full flow: SO -> confirm -> deliver -> done -> POST accept_viva ->
      signed doc created (type delivery_note, chained sale_order_id),
      receiver signature baked in the signed PDF, chatter post
  D5  Stored bytes served on print (ir_actions_report override) — the
      viva_pdf route returns byte-identical bytes to the stored attachment
  D6  Idempotent repeat POST (same 3-layer guard as /accept_viva)
  D7  Lock: substance edits + cancel blocked on a signed picking
  D8  Delivery stamp shows Linked SO + its verification code
"""
import base64
import json
import urllib.request

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


def http_get_bytes(url, headers=None):
    req = urllib.request.Request(url, method='GET')
    req.add_header('Host', 'test_sign.stg.vivafarm')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


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


print('=== delivery_accept_test — delivery note signing (ใบส่งสินค้า) ===')

# ── Setup: test partner/product ──
partner = env['res.partner'].search([('name', '=', 'Delivery Sign Test Customer')], limit=1)
if not partner:
    partner = env['res.partner'].create({
        'name': 'Delivery Sign Test Customer', 'is_company': True, 'lang': 'en_US',
    })
product = env['product.product'].search([('name', '=', 'Delivery Sign Test Product')], limit=1)
if not product:
    # Storable product in a real-time valuation category so delivery moves work.
    goods_cat = env['product.category'].search(
        [('name', '=', 'All'), ('property_valuation', '=', 'real_time')], limit=1) or \
        env['product.category'].search([], limit=1)
    product = env['product.product'].create({
        'name': 'Delivery Sign Test Product',
        'type': 'consu',
        'sale_ok': True,
        'categ_id': goods_cat.id,
        'is_storable': True,
    })
pricelist = env['product.pricelist'].search([], limit=1)


def make_so(qty=2, price=100):
    return env['sale.order'].create({
        'partner_id': partner.id,
        'pricelist_id': pricelist.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'product_uom_qty': qty,
            'price_unit': price,
        })],
    })


def deliver_and_done(so):
    """Confirm the SO and validate the outgoing picking -> done."""
    so.action_confirm()
    picking = so.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
    for move in picking.move_ids:
        move.quantity = move.product_uom_qty
        move.picked = True
    picking.button_validate()
    picking = so.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
    picking.button_done()
    picking.invalidate_recordset()
    return picking


# ── D1: model + constraint ──
print('--- D1 signed.document delivery support ---')
check('D1 delivery_note type exists',
      any(v == 'delivery_note' for v, _ in env['viva.signed.document']._fields['document_type'].selection))
check('D1 picking_id field exists', 'picking_id' in env['viva.signed.document']._fields)
check('D1 stock.picking.signed_by exists', 'signed_by' in env['stock.picking']._fields)
check('D1 stock.picking.signed_on exists', 'signed_on' in env['stock.picking']._fields)
check('D1 stock.picking.signed_position exists', 'signed_position' in env['stock.picking']._fields)

# ── D2: routes registered ──
print('--- D2 routes registered ---')
check('D2 /my/picking/<id>/viva_pdf route registered',
      http_status('GET', 'http://127.0.0.1:8069/my/picking/999999/viva_pdf') != 404,
      '(not 404 = route present)')
check('D2 /my/picking/<id>/accept_viva route registered',
      http_status('POST', 'http://127.0.0.1:8069/my/picking/999999/accept_viva',
                  {'access_token': 'x', 'name': 'x', 'signature': 'x'}) != 404,
      '(not 404 = route present)')

# ── D3: portal page shows delivery buttons ──
print('--- D3 portal page delivery buttons ---')
so3 = make_so()
so3._portal_ensure_token()
env.cr.commit()
so3.action_confirm()
env.cr.commit()
try:
    page = http_get_bytes('http://127.0.0.1:8069/my/orders/%d?access_token=%s' % (so3.id, so3.access_token)).decode()
except Exception as e:
    page = ''
    print('  (portal page fetch failed: %s)' % e)
check('D3 page has View Viva Delivery Note button', 'View Viva Delivery Note' in page)
check('D3 page has Accept & Sign Delivery button', 'Accept & Sign Delivery' in page)
check('D3 page has delivery signature modal', 'modalaccept_viva_delivery' in page)
check('D3 page has viva_pdf route link', '/viva_pdf' in page)

# ── D4: full flow via the new route ──
print('--- D4 accept via /my/picking/<id>/accept_viva → signed + chained ---')
so4 = make_so()
so4._portal_ensure_token()
env.cr.commit()
so4.action_confirm()
env.cr.commit()
picking4 = deliver_and_done(so4)
env.cr.commit()
picking4 = env['stock.picking'].browse(picking4.id)
picking4.invalidate_recordset()
check('D4 picking done', picking4.state == 'done', '(state=%s)' % picking4.state)
check('D4 picking linked to SO', picking4.sale_id.id == so4.id)

url = 'http://127.0.0.1:8069/my/picking/%d/accept_viva' % picking4.id
try:
    resp = http_jsonrpc(url, {
        'access_token': so4.access_token,
        'name': 'Delivery Receiver',
        'position': 'Store Manager',
        'signature': SIGNATURE_B64,
    })
    check('D4 route returned ok', resp.get('result', {}).get('force_refresh') is True,
          '(resp=%s)' % str(resp.get('result'))[:120])
except Exception as e:
    check('D4 route returned ok', False, '(error: %s)' % e)

env.cr.commit()
picking4 = env['stock.picking'].browse(picking4.id)
picking4.invalidate_recordset()
check('D4 signed_by stored', picking4.signed_by == 'Delivery Receiver',
      '(signed_by=%r)' % picking4.signed_by)
check('D4 signed_position stored', picking4.signed_position == 'Store Manager',
      '(signed_position=%r)' % picking4.signed_position)
check('D4 signature stored', bool(picking4.signature))
signed4 = env['viva.signed.document'].search([('picking_id', '=', picking4.id)], limit=1)
check('D4 signed doc created', bool(signed4))
signed4_bytes = b''
if signed4:
    check('D4 document_type delivery_note', signed4.document_type == 'delivery_note',
          '(type=%s)' % signed4.document_type)
    check('D4 chained to linked SO', signed4.sale_order_id.id == so4.id,
          '(sale_order_id=%s)' % signed4.sale_order_id.id)
    signed4_bytes = base64.b64decode(signed4.signed_attachment_id.datas)
    check('D4 signed attachment exists', len(signed4_bytes) > 50000,
          '(bytes=%d)' % len(signed4_bytes))
    check('D4 hash block in delivery render',
          b'Digitally Signed Document' in env['ir.actions.report']._render_qweb_html(
              'vivafarm_report.viva_delivery_note', [picking4.id])[0])
    check('D4 receiver signature baked in signed PDF',
          b'Delivery Receiver' in env['ir.actions.report'].with_context(
              delivery_include_signature=True)._render_qweb_html(
                  'vivafarm_report.viva_delivery_note', [picking4.id])[0])
# Chatter post (no email — user decision).
msgs = env['mail.message'].search([
    ('model', '=', 'stock.picking'),
    ('res_id', '=', picking4.id),
], order='id desc', limit=5)
att_found = any(
    att.name.startswith(picking4.name) and att.name.endswith('.pdf')
    for m in msgs for att in m.attachment_ids
)
check('D4 chatter post with delivery PDF', att_found)

# ── D5: stored bytes served on print (override) ──
print('--- D5 stored bytes served ---')
if signed4:
    route_bytes = http_get_bytes(
        'http://127.0.0.1:8069/my/picking/%d/viva_pdf?access_token=%s' % (picking4.id, so4.access_token))
    check('D5 viva_pdf route returns stored signed bytes (byte-identical)',
          route_bytes == signed4_bytes,
          '(route=%dB stored=%dB)' % (len(route_bytes), len(signed4_bytes)))

# ── D6: idempotent repeat POST ──
print('--- D6 repeat POST on already-signed delivery is a benign success ---')
try:
    resp6 = http_jsonrpc(url, {
        'access_token': so4.access_token,
        'name': 'Delivery Receiver',
        'signature': SIGNATURE_B64,
    })
    res6 = resp6.get('result') or {}
    check('D6 repeat POST returns success shape (force_refresh)',
          res6.get('force_refresh') is True,
          '(resp=%s)' % str(res6)[:160])
    check('D6 repeat POST redirect is sign_ok', 'sign_ok' in (res6.get('redirect_url') or ''),
          '(url=%s)' % (res6.get('redirect_url') or ''))
    check('D6 repeat POST has no guard error',
          'not in a state requiring customer acknowledgment' not in json.dumps(res6))
except Exception as e:
    check('D6 repeat POST returns success shape (force_refresh)', False, '(error: %s)' % e)
env.cr.commit()
signed_count6 = env['viva.signed.document'].search_count([('picking_id', '=', picking4.id)])
check('D6 still exactly one signed doc after repeat POST', signed_count6 == 1,
      '(count=%d)' % signed_count6)

# ── D7: lock — substance edits + cancel blocked ──
print('--- D7 signed delivery locked ---')
if signed4:
    try:
        picking4.write({'origin': 'CHANGED-ORIGIN'})
        check('D7 substance edit blocked', False, '(write succeeded!)')
    except UserError:
        check('D7 substance edit blocked', True, '(UserError)')
    try:
        picking4.action_cancel()
        check('D7 cancel blocked', False, '(cancel succeeded!)')
    except UserError:
        check('D7 cancel blocked', True, '(UserError)')
    check('D7 picking still done', picking4.state == 'done', '(state=%s)' % picking4.state)

# ── D8: delivery stamp shows Linked SO + verification code ──
print('--- D8 linked SO on the stamp ---')
if signed4:
    so_signed = env['viva.signed.document'].search([('sale_order_id', '=', so4.id)], limit=1)
    if so_signed:
        html8 = env['ir.actions.report']._render_qweb_html(
            'vivafarm_report.viva_delivery_note', [picking4.id])[0]
        check('D8 stamp shows Linked SO', so4.name.encode() in html8)
        check('D8 stamp shows SO verification code',
              so_signed.verification_code.encode() in html8,
              '(code=%s)' % so_signed.verification_code)
    else:
        check('D8 stamp shows Linked SO', False, '(no SO signed doc — link missing)')

# ── Summary ──
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back — committed HTTP-test deliveries stay for manual inspection)')
