#!/usr/bin/env python3
"""delivery_accept_test — end-to-end test for the delivery note signing flow.

Run against test_sign (vivafarm_report + vivafarm_document_sign installed):

    sudo -u odoo odoo shell -d test_sign --no-http \
      --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/opt/odoo-custom-addons \
      < delivery_accept_test_2027.py

WHY THIS FEATURE (user design 2026-08-18, Option D):
  Delivery state machine becomes Ready > In Transit > Done. "Ship & Send DN"
  (NEW button, next to Validate) moves a Ready delivery to In Transit and
  emails the customer the Viva DN PDF + portal link. The customer signs via
  "Accept & Sign Delivery" in the portal — the route runs the
  Validate-equivalent (_complete_delivery: stock moves + done), then hashes
  + RSA-signs the DN. Validate stays untouched (Path A direct-done, no sign).
  Force Done (user choice A) is the fallback for never-signed deliveries.

Checks:
  D1  Model: in_transit field + state selection has in_transit + compute
  D2  Routes registered: /my/picking/<id>/viva_pdf + /accept_viva
  D3  Portal page: yellow In Transit badge + Accept & Sign Delivery button
      (button ONLY on in_transit — NOT on done)
  D4  Ship & Send DN: state in_transit + email with DN PDF + portal link
  D5  Full flow: sign in transit -> _complete_delivery (state done, stock
      moved) + signed doc + chain + byte-identical stored bytes + chatter
  D6  Idempotent repeat POST
  D7  Lock: substance edits + cancel blocked on signed delivery
  D8  Path A (Validate): done WITHOUT signature — no sign button, no signed
      doc, route rejects (not in transit)
  D9  Force Done: in_transit -> done without signature (fallback), no signed
      doc, route rejects
  D10 Delivery stamp shows Linked SO (no masquerade)
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


def confirm_and_ready(so):
    """Confirm the SO and return the outgoing picking (state assigned/ready)."""
    so.action_confirm()
    picking = so.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
    picking.move_ids._action_assign()
    picking.invalidate_recordset()
    return picking


def validate_direct(picking):
    """Path A: stock Validate-equivalent — quantities + _action_done -> done."""
    for move in picking.move_ids:
        move.quantity = move.product_uom_qty
        move.picked = True
    picking._action_done()
    picking.invalidate_recordset()
    return picking


# ── D1: model + state machine ──
print('--- D1 in_transit model ---')
check('D1 in_transit field exists', 'in_transit' in env['stock.picking']._fields)
states = dict(env['stock.picking']._fields['state'].selection)
check('D1 state selection has in_transit', 'in_transit' in states,
      '(states=%s)' % sorted(states.keys()))
check('D1 stock.picking.signed_by exists', 'signed_by' in env['stock.picking']._fields)
check('D1 viva.signed.document picking_id exists', 'picking_id' in env['viva.signed.document']._fields)

# ── D2: routes registered ──
print('--- D2 routes registered ---')
check('D2 /my/picking/<id>/viva_pdf route registered',
      http_status('GET', 'http://127.0.0.1:8069/my/picking/999999/viva_pdf') != 404,
      '(not 404 = route present)')
check('D2 /my/picking/<id>/accept_viva route registered',
      http_status('POST', 'http://127.0.0.1:8069/my/picking/999999/accept_viva',
                  {'access_token': 'x', 'name': 'x', 'signature': 'x'}) != 404,
      '(not 404 = route present)')

# ── D3: portal page — In Transit badge + sign button only in transit ──
print('--- D3 portal page (in transit) ---')
so3 = make_so()
so3._portal_ensure_token()
env.cr.commit()
picking3 = confirm_and_ready(so3)
env.cr.commit()
picking3.action_ship_and_send_dn()
env.cr.commit()
picking3 = env['stock.picking'].browse(picking3.id)
picking3.invalidate_recordset()
check('D3 ship & send -> state in_transit', picking3.state == 'in_transit',
      '(state=%s)' % picking3.state)
try:
    page = http_get_bytes('http://127.0.0.1:8069/my/orders/%d?access_token=%s' % (so3.id, so3.access_token)).decode()
except Exception as e:
    page = ''
    print('  (portal page fetch failed: %s)' % e)
check('D3 page has In Transit badge', 'In Transit' in page)
check('D3 page has Accept & Sign Delivery button', 'Accept & Sign Delivery' in page)
check('D3 page has View Viva Delivery Note button', 'View Viva Delivery Note' in page)
check('D3 page has delivery signature modal', 'modalaccept_viva_delivery' in page)
check('D3 page has viva_pdf route link', '/viva_pdf' in page)

# ── D4: ship & send email with DN PDF + portal link ──
print('--- D4 Ship & Send DN email ---')
msgs4 = env['mail.message'].search([
    ('model', '=', 'stock.picking'),
    ('res_id', '=', picking3.id),
], order='id desc', limit=5)
dn_att = any(
    att.name.startswith(picking3.name) and att.name.endswith('.pdf')
    for m in msgs4 for att in m.attachment_ids
)
check('D4 email has DN PDF attachment', dn_att)

# ── D5: full flow via the new route (in transit -> sign -> done + signed) ──
print('--- D5 sign in transit -> complete + signed + chained ---')
so5 = make_so()
so5._portal_ensure_token()
env.cr.commit()
picking5 = confirm_and_ready(so5)
env.cr.commit()
picking5.action_ship_and_send_dn()
env.cr.commit()
picking5 = env['stock.picking'].browse(picking5.id)
picking5.invalidate_recordset()
check('D5 picking in_transit before sign', picking5.state == 'in_transit',
      '(state=%s)' % picking5.state)
url = 'http://127.0.0.1:8069/my/picking/%d/accept_viva' % picking5.id
try:
    resp = http_jsonrpc(url, {
        'access_token': so5.access_token,
        'name': 'Delivery Receiver',
        'position': 'Store Manager',
        'signature': SIGNATURE_B64,
    })
    check('D5 route returned ok', resp.get('result', {}).get('force_refresh') is True,
          '(resp=%s)' % str(resp.get('result'))[:120])
except Exception as e:
    check('D5 route returned ok', False, '(error: %s)' % e)

env.cr.commit()
picking5 = env['stock.picking'].browse(picking5.id)
picking5.invalidate_recordset()
check('D5 state done after sign', picking5.state == 'done', '(state=%s)' % picking5.state)
check('D5 in_transit flag cleared', not picking5.in_transit)
check('D5 signed_by stored', picking5.signed_by == 'Delivery Receiver',
      '(signed_by=%r)' % picking5.signed_by)
check('D5 signed_position stored', picking5.signed_position == 'Store Manager',
      '(signed_position=%r)' % picking5.signed_position)
check('D5 signature stored', bool(picking5.signature))
signed5 = env['viva.signed.document'].search([('picking_id', '=', picking5.id)], limit=1)
check('D5 signed doc created', bool(signed5))
signed5_bytes = b''
if signed5:
    check('D5 document_type delivery_note', signed5.document_type == 'delivery_note',
          '(type=%s)' % signed5.document_type)
    check('D5 chained to linked SO', signed5.sale_order_id.id == so5.id,
          '(sale_order_id=%s)' % signed5.sale_order_id.id)
    signed5_bytes = base64.b64decode(signed5.signed_attachment_id.datas)
    check('D5 signed attachment exists', len(signed5_bytes) > 50000,
          '(bytes=%d)' % len(signed5_bytes))
    check('D5 hash block in delivery render',
          b'Digitally Signed Document' in env['ir.actions.report']._render_qweb_html(
              'vivafarm_report.viva_delivery_note', [picking5.id])[0])
    check('D5 receiver signature baked in signed PDF',
          b'Delivery Receiver' in env['ir.actions.report'].with_context(
              delivery_include_signature=True)._render_qweb_html(
                  'vivafarm_report.viva_delivery_note', [picking5.id])[0])
msgs5 = env['mail.message'].search([
    ('model', '=', 'stock.picking'),
    ('res_id', '=', picking5.id),
], order='id desc', limit=5)
att_found = any(
    att.name.startswith(picking5.name) and att.name.endswith('.pdf')
    for m in msgs5 for att in m.attachment_ids
)
check('D5 chatter post with delivery PDF', att_found)
# Stock actually moved (Validate-equivalent ran)
moves_done = all(m.state == 'done' for m in picking5.move_ids)
check('D5 stock moves done after sign', moves_done)

# ── Stored bytes served on print (override) ──
print('--- D5b stored bytes served ---')
if signed5:
    route_bytes = http_get_bytes(
        'http://127.0.0.1:8069/my/picking/%d/viva_pdf?access_token=%s' % (picking5.id, so5.access_token))
    check('D5b viva_pdf route returns stored signed bytes (byte-identical)',
          route_bytes == signed5_bytes,
          '(route=%dB stored=%dB)' % (len(route_bytes), len(signed5_bytes)))

# ── D6: idempotent repeat POST ──
print('--- D6 repeat POST on already-signed delivery is a benign success ---')
try:
    resp6 = http_jsonrpc(url, {
        'access_token': so5.access_token,
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
          'not in transit' not in json.dumps(res6))
except Exception as e:
    check('D6 repeat POST returns success shape (force_refresh)', False, '(error: %s)' % e)
env.cr.commit()
signed_count6 = env['viva.signed.document'].search_count([('picking_id', '=', picking5.id)])
check('D6 still exactly one signed doc after repeat POST', signed_count6 == 1,
      '(count=%d)' % signed_count6)

# ── D7: lock — substance edits + cancel blocked ──
print('--- D7 signed delivery locked ---')
if signed5:
    try:
        picking5.write({'origin': 'CHANGED-ORIGIN'})
        check('D7 substance edit blocked', False, '(write succeeded!)')
    except UserError:
        check('D7 substance edit blocked', True, '(UserError)')
    try:
        picking5.action_cancel()
        check('D7 cancel blocked', False, '(cancel succeeded!)')
    except UserError:
        check('D7 cancel blocked', True, '(UserError)')
    check('D7 picking still done', picking5.state == 'done', '(state=%s)' % picking5.state)

# ── D8: Path A — Validate direct: done WITHOUT signature ──
print('--- D8 Path A (Validate) done without sign ---')
so8 = make_so()
so8._portal_ensure_token()
env.cr.commit()
picking8 = confirm_and_ready(so8)
env.cr.commit()
validate_direct(picking8)
env.cr.commit()
picking8 = env['stock.picking'].browse(picking8.id)
picking8.invalidate_recordset()
check('D8 Path A state done', picking8.state == 'done', '(state=%s)' % picking8.state)
check('D8 no signed doc on Path A', not env['viva.signed.document'].search(
    [('picking_id', '=', picking8.id)], limit=1))
try:
    page8 = http_get_bytes('http://127.0.0.1:8069/my/orders/%d?access_token=%s' % (so8.id, so8.access_token)).decode()
except Exception as e:
    page8 = ''
    print('  (portal page fetch failed: %s)' % e)
check('D8 no Accept & Sign button on done-without-sign', 'Accept & Sign Delivery' not in page8)
# Route rejects: not in transit
try:
    resp8 = http_jsonrpc('http://127.0.0.1:8069/my/picking/%d/accept_viva' % picking8.id, {
        'access_token': so8.access_token,
        'name': 'Delivery Receiver',
        'signature': SIGNATURE_B64,
    })
    check('D8 route rejects done-without-sign', 'not in transit' in json.dumps(resp8),
          '(resp=%s)' % str(resp8.get('result'))[:120])
except Exception as e:
    check('D8 route rejects done-without-sign', False, '(error: %s)' % e)

# ── D9: Force Done fallback (user choice A) ──
print('--- D9 Force Done fallback ---')
so9 = make_so()
so9._portal_ensure_token()
env.cr.commit()
picking9 = confirm_and_ready(so9)
env.cr.commit()
picking9.action_ship_and_send_dn()
env.cr.commit()
picking9 = env['stock.picking'].browse(picking9.id)
picking9.invalidate_recordset()
check('D9 in_transit before force', picking9.state == 'in_transit')
picking9.action_force_done()
env.cr.commit()
picking9 = env['stock.picking'].browse(picking9.id)
picking9.invalidate_recordset()
check('D9 force done -> state done', picking9.state == 'done', '(state=%s)' % picking9.state)
check('D9 in_transit flag cleared', not picking9.in_transit)
check('D9 no signed doc on force done', not env['viva.signed.document'].search(
    [('picking_id', '=', picking9.id)], limit=1))
# Route rejects: done without signature
try:
    resp9 = http_jsonrpc('http://127.0.0.1:8069/my/picking/%d/accept_viva' % picking9.id, {
        'access_token': so9.access_token,
        'name': 'Delivery Receiver',
        'signature': SIGNATURE_B64,
    })
    check('D9 route rejects force-done', 'not in transit' in json.dumps(resp9),
          '(resp=%s)' % str(resp9.get('result'))[:120])
except Exception as e:
    check('D9 route rejects force-done', False, '(error: %s)' % e)

# ── D10: delivery stamp shows Linked SO (no masquerade) ──
print('--- D10 linked SO on the stamp ---')
if signed5:
    so_signed = env['viva.signed.document'].search([
        ('sale_order_id', '=', so5.id),
        ('document_type', '=', 'sale_order'),
    ], limit=1)
    html10 = env['ir.actions.report']._render_qweb_html(
        'vivafarm_report.viva_delivery_note', [picking5.id])[0]
    check('D10 stamp shows Linked SO', so5.name.encode() in html10)
    check('D10 no SO code when SO unsigned',
          ('Code: %s' % signed5.verification_code).encode() not in html10,
          '(delivery code must not appear as SO code)')

# ── Summary ──
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back — committed HTTP-test deliveries stay for manual inspection)')
