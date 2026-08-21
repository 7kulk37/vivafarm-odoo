#!/usr/bin/env python3
"""manual_upload_edge_test — edge cases of the manual hand-signed upload flow
(SO / delivery / invoice / slip) plus the digital->manual seam.

Covers the holes the happy-path test (manual_upload_test_2027.py) leaves open:

  E1  Missing access_token  -> redirect, NO record sealed
  E2  Forged token          -> redirect, NO record sealed
  E3  Disallowed mimetype   -> upload_bad_type redirect, NO record
  E4  >10 MB file           -> upload_too_large redirect, NO record
  E5  Missing uploader name -> upload_name_required redirect, NO record
  E6  Missing confirm box   -> upload_confirm_required redirect, NO record
  E7  Zero-byte file        -> upload_no_file redirect, NO record
  E8  Same bytes re-upload  -> converges on SAME record (count stays 1)
  E9  Different bytes re-upload -> converges, FIRST bytes kept (sha unchanged)
  E10 Digital-sealed doc + manual upload -> converges on the DIGITAL record,
      channel stays 'digital', count stays 1 (one seal per document)
  E11 No-email partner      -> route still seals, no exception notification
  E12 Slip-before-payment   -> _create_manual_record(payment.transaction)
      works without a payment_id (no crash, link field empty)
  E13 Delivery route        -> seals with picking link, redirect upload_ok
  E14 Unicode/odd filename  -> seals fine
  E15 Invoice route minimal-flow partner -> document_type = tax_invoice

All HTTP probes use a NO-REDIRECT opener so we assert the Location header
(303 + ?message=...) instead of depending on portal alert rendering.
"""
import base64
import hashlib
import urllib.request
import urllib.error
import uuid

from odoo import fields

PASS = 0
FAIL = 0
STS = (302, 303)


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  PASS: %s %s' % (name, detail))
    else:
        FAIL += 1
        print('  FAIL: %s %s' % (name, detail))


PNG_B64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
FILE_A = base64.b64decode(PNG_B64)
FILE_B = b'0' * 4096  # different bytes for the re-upload test
SHA_A = hashlib.sha256(FILE_A).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post(url, fields_dict, files):
    """POST multipart WITHOUT following redirects; returns (status, headers, body)."""
    boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
    body = b''
    for k, v in fields_dict.items():
        body += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                 % (boundary, k, v)).encode()
    for k, (filename, mimetype, data) in files.items():
        body += ('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\n'
                 'Content-Type: %s\r\n\r\n' % (boundary, k, filename, mimetype)).encode()
        body += data + b'\r\n'
    body += ('--%s--\r\n' % boundary).encode()
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Host', 'test_sign.stg.vivafarm')
    req.add_header('Content-Type', 'multipart/form-data; boundary=%s' % boundary)
    opener = urllib.request.build_opener(NoRedirect)
    try:
        resp = opener.open(req, timeout=30)
        return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def loc_has(headers, needle):
    return needle in (headers.get('Location') or '')


def count_manual(record_id, model='sale.order', doc_type='sale_order'):
    return env['viva.signed.document'].sudo().search_count([
        ('odoo_model', '=', model),
        ('odoo_record_id', '=', record_id),
        ('document_type', '=', doc_type),
        ('channel', '=', 'manual'),
    ])


def get_signed(record_id, model='sale.order', doc_type='sale_order'):
    return env['viva.signed.document'].sudo().search([
        ('odoo_model', '=', model),
        ('odoo_record_id', '=', record_id),
        ('document_type', '=', doc_type),
    ], limit=1)


print('=== manual_upload_edge_test — edge cases (SO / delivery / invoice / slip / seam) ===')

Model = env['viva.signed.document'].sudo()

# ── Setup: partner + products + pricelist ──
partner = env['res.partner'].search([('name', '=', 'SO Edge Customer')], limit=1)
if not partner:
    partner = env['res.partner'].create({
        'name': 'SO Edge Customer', 'is_company': True, 'lang': 'en_US',
        'email': 'so-edge@example.invalid',
    })
service = env['product.product'].search([('name', '=', 'SO Edge Service')], limit=1)
if not service:
    service = env['product.product'].create({'name': 'SO Edge Service', 'type': 'service', 'sale_ok': True})
    income = env['account.account'].search([('account_type', '=', 'income')], limit=1)
    service.write({'property_account_income_id': income.id})
stock_prod = env['product.product'].search([('name', '=', 'SO Edge Stock')], limit=1)
if not stock_prod:
    # This Odoo 19 build uses type='consu' ('product'/'stor' don't exist —
    # selection is consu/service/combo); consu goods still drive deliveries.
    stock_prod = env['product.product'].create({'name': 'SO Edge Stock', 'type': 'consu', 'sale_ok': True})
    income = env['account.account'].search([('account_type', '=', 'income')], limit=1)
    expense = env['account.account'].search([('account_type', '=', 'expense')], limit=1)
    stock_prod['property_account_income_id'] = income.id
    stock_prod['property_account_expense_id'] = expense.id
pricelist = env['product.pricelist'].search([], limit=1)


def new_so(product=service, qty=1):
    so = env['sale.order'].create({
        'partner_id': partner.id,
        'pricelist_id': pricelist.id,
        'order_line': [(0, 0, {
            'product_id': product.id, 'product_uom_qty': qty, 'price_unit': 10,
        })],
    })
    so._portal_ensure_token()
    return so


def so_url(so_id, suffix='confirm_viva'):
    return 'http://127.0.0.1:8069/my/orders/%d/%s' % (so_id, suffix)


# ── E1-E7: validation + token guards (each on a FRESH order) ──
print('--- E1-E7 guards ---')
so = new_so()
env.cr.commit()
st, hdrs, body = post(so_url(so.id), {
    'uploader_name': 'X', 'confirm': '1',
}, {'upload': ('ok.png', 'image/png', FILE_A)})
check('E1 no-token -> 303 redirect', st in STS, '(status=%d)' % st)
check('E1 not upload_ok (no location)', not loc_has(hdrs, 'upload_ok'))
check('E1 no record sealed', count_manual(so.id) == 0)

so = new_so()
env.cr.commit()
st, hdrs, body = post(so_url(so.id), {
    'access_token': 'FORGEDTOKEN123', 'uploader_name': 'X', 'confirm': '1',
}, {'upload': ('ok.png', 'image/png', FILE_A)})
check('E2 forged-token -> 303', st in STS, '(status=%d)' % st)
check('E2 no record sealed', count_manual(so.id) == 0)

so = new_so()
env.cr.commit()
st, hdrs, body = post(so_url(so.id), {
    'access_token': so.access_token, 'uploader_name': 'X', 'confirm': '1',
}, {'upload': ('evil.pdf', 'text/plain', b'MZ...')})
check('E3 bad type -> upload_bad_type', st in STS and loc_has(hdrs, 'upload_bad_type'),
      '(status=%d loc=%s)' % (st, hdrs.get('Location')))
check('E3 no record sealed', count_manual(so.id) == 0)

so = new_so()
env.cr.commit()
st, hdrs, body = post(so_url(so.id), {
    'access_token': so.access_token, 'uploader_name': 'X', 'confirm': '1',
}, {'upload': ('big.png', 'image/png', b'0' * (10 * 1024 * 1024 + 1))})
check('E4 >10MB -> upload_too_large', st in STS and loc_has(hdrs, 'upload_too_large'),
      '(status=%d loc=%s)' % (st, hdrs.get('Location')))
check('E4 no record sealed', count_manual(so.id) == 0)

so = new_so()
env.cr.commit()
st, hdrs, body = post(so_url(so.id), {
    'access_token': so.access_token, 'uploader_name': '   ', 'confirm': '1',
}, {'upload': ('ok.png', 'image/png', FILE_A)})
check('E5 blank name -> upload_name_required', st in STS and loc_has(hdrs, 'upload_name_required'),
      '(status=%d loc=%s)' % (st, hdrs.get('Location')))
check('E5 no record sealed', count_manual(so.id) == 0)

so = new_so()
env.cr.commit()
st, hdrs, body = post(so_url(so.id), {
    'access_token': so.access_token, 'uploader_name': 'X', 'confirm': '',
}, {'upload': ('a.png', 'image/png', FILE_A)})
check('E6 no confirm -> upload_confirm_required', st in STS and loc_has(hdrs, 'upload_confirm_required'),
      '(status=%d loc=%s)' % (st, hdrs.get('Location')))
check('E6 no record sealed', count_manual(so.id) == 0)

so = new_so()
env.cr.commit()
st, hdrs, body = post(so_url(so.id), {
    'access_token': so.access_token, 'uploader_name': 'X', 'confirm': '1',
}, {'upload': ('empty.png', 'image/png', b'')})
check('E7 zero-byte -> upload_no_file', st in STS and loc_has(hdrs, 'upload_no_file'),
      '(status=%d loc=%s)' % (st, hdrs.get('Location')))
check('E7 no record sealed', count_manual(so.id) == 0)

# ── E8/E9: re-upload converges, first bytes win ──
print('--- E8/E9 idempotency + first-bytes-win ---')
so = new_so()
env.cr.commit()
st, hdrs, body = post(so_url(so.id), {
    'access_token': so.access_token, 'uploader_name': 'First', 'confirm': '1',
}, {'upload': ('a.png', 'image/png', FILE_A)})
check('E8 first upload ok', st in STS and loc_has(hdrs, 'upload_ok'), '(status=%d)' % st)
env.cr.commit()
r1 = get_signed(so.id)
env.cr.commit()
st, hdrs, body = post(so_url(so.id), {
    'access_token': so.access_token, 'uploader_name': 'Second', 'confirm': '1',
}, {'upload': ('a2.png', 'image/png', FILE_A)})
env.cr.commit()
so.invalidate_recordset()
r2 = get_signed(so.id)
check('E8 same-bytes re-upload converges', bool(r1) and r2.id == r1.id, '(r1=%s r2=%s)' % (r1.id, r2.id))
check('E8 count stays 1', count_manual(so.id) == 1)

st, hdrs, body = post(so_url(so.id), {
    'access_token': so.access_token, 'uploader_name': 'Third', 'confirm': '1',
}, {'upload': ('b.png', 'image/png', FILE_B)})
env.cr.commit()
so.invalidate_recordset()
r3 = get_signed(so.id)
check('E9 diff-bytes re-upload -> same record', bool(r3) and r3.id == r1.id, '(r1=%s r3=%s)' % (r1.id, r3.id))
check('E9 first bytes kept (sha unchanged)', r3.pdf_sha256 == SHA_A, '(sha=%s)' % r3.pdf_sha256[:12])

# ── E10: digital -> manual seam ──
print('--- E10 digital->manual seam (one seal per doc) ---')
so = new_so()
env.cr.commit()
Model.create({
    'document_number': so.name,
    'document_type': 'sale_order',
    'odoo_model': 'sale.order',
    'odoo_record_id': so.id,
    'channel': 'digital',
    'state': 'signed',
    'revision': 1,
})
env.cr.commit()
so.invalidate_recordset()
st, hdrs, body = post(so_url(so.id), {
    'access_token': so.access_token, 'uploader_name': 'ManualLater', 'confirm': '1',
}, {'upload': ('hand.png', 'image/png', FILE_A)})
env.cr.commit()
so.invalidate_recordset()
recs = env['viva.signed.document'].sudo().search([
    ('odoo_model', '=', 'sale.order'),
    ('odoo_record_id', '=', so.id),
    ('document_type', '=', 'sale_order'),
])
check('E10 upload route on digital doc ok', st in STS and loc_has(hdrs, 'upload_ok'),
      '(status=%d loc=%s)' % (st, hdrs.get('Location')))
check('E10 exactly ONE signed record', len(recs) == 1, '(n=%d)' % len(recs))
check('E10 channel stayed digital', bool(recs) and recs.channel == 'digital',
      '(channel=%s)' % (recs.channel if recs else 'n/a'))

# ── E11: no-email partner still works ──
print('--- E11 no-email partner ---')
partner_noemail = env['res.partner'].search([('name', '=', 'SO No Email Edge')], limit=1)
if not partner_noemail:
    partner_noemail = env['res.partner'].create({
        'name': 'SO No Email Edge', 'is_company': True, 'lang': 'en_US',
    })  # NO email on purpose
so = env['sale.order'].create({
    'partner_id': partner_noemail.id, 'pricelist_id': pricelist.id,
    'order_line': [(0, 0, {'product_id': service.id, 'product_uom_qty': 1, 'price_unit': 10})],
})
so._portal_ensure_token()
env.cr.commit()
exc_before = env['mail.notification'].search_count([
    ('res_partner_id', '=', partner_noemail.id),
    ('notification_status', '=', 'exception'),
])
st, hdrs, body = post(so_url(so.id), {
    'access_token': so.access_token, 'uploader_name': 'NoMail', 'confirm': '1',
}, {'upload': ('a.png', 'image/png', FILE_A)})
env.cr.commit()
exc_after = env['mail.notification'].search_count([
    ('res_partner_id', '=', partner_noemail.id),
    ('notification_status', '=', 'exception'),
])
check('E11 no-email partner upload ok', st in STS and loc_has(hdrs, 'upload_ok'),
      '(status=%d)' % st)
check('E11 no NEW exception notification', exc_after == exc_before,
      '(before=%d after=%d)' % (exc_before, exc_after))

# ── E12: slip before payment ──
print('--- E12 slip-before-payment ---')
prov = env['payment.provider'].search([('code', '=', 'custom')], limit=1)
check('E12 custom provider present (fixture)', bool(prov))
if prov:
    pm = prov.payment_method_ids[:1] or env['payment.method'].search([], limit=1)
    tx = env['payment.transaction'].create({
        'provider_id': prov.id, 'partner_id': partner.id,
        'amount': 100.0, 'currency_id': env.ref('base.THB').id,
        'reference': 'TXEDGE-%s' % uuid.uuid4().hex[:8],
        'payment_method_id': pm.id if pm else False,
    })
    slip = Model._create_manual_record(
        model='payment.transaction', record_id=tx.id,
        document_type='payment_slip', document_number=tx.reference,
        filename='slip.png', mimetype='image/png', data=FILE_A,
        uploader_name='SlipGuy', uploader_ip='10.0.0.9', uploader_agent='EdgeAgent',
    )
    check('E12 slip record created without payment_id', bool(slip))
    check('E12 no crash (payment_id empty)', not slip.payment_id)

# ── E13: delivery route resolves + upload_ok ──
print('--- E13 delivery confirm route ---')
so = new_so(product=stock_prod)
so.action_confirm()
pick = so.picking_ids[:1]
# stock.picking has NO portal.mixin / _portal_ensure_token — the delivery
# route checks access via the SO's access_token (the modal posts it).
env.cr.commit()
url = 'http://127.0.0.1:8069/my/picking/%d/confirm_viva' % pick.id
st, hdrs, body = post(url, {
    'access_token': so.access_token, 'uploader_name': 'Deliverer', 'confirm': '1',
}, {'upload': ('a.png', 'image/png', FILE_A)})
env.cr.commit()
rec = env['viva.signed.document'].sudo().search([
    ('picking_id', '=', pick.id), ('document_type', '=', 'delivery_note'),
    ('channel', '=', 'manual')], limit=1)
check('E13 delivery route ok', st in STS and loc_has(hdrs, 'upload_ok'),
      '(status=%d loc=%s)' % (st, hdrs.get('Location')))
check('E13 picking link set', bool(rec) and rec.picking_id.id == pick.id,
      '(pick=%s)' % (rec.picking_id.id if rec else 'n/a'))

# ── E14: unicode filename ──
print('--- E14 odd filename ---')
so = new_so()
env.cr.commit()
st, hdrs, body = post(so_url(so.id), {
    'access_token': so.access_token, 'uploader_name': 'Uni', 'confirm': '1',
}, {'upload': ('สแกน-ลงนาม ใบเสนอราคา (2).png', 'image/png', FILE_A)})
env.cr.commit()
rec = get_signed(so.id)
check('E14 unicode filename ok', st in STS and loc_has(hdrs, 'upload_ok'), '(status=%d)' % st)
check('E14 filename stored', bool(rec) and 'สแกน' in rec.source_filename,
      '(fn=%s)' % (rec.source_filename if rec else ''))

# ── E15: invoice route, minimal-flow partner -> tax_invoice ──
print('--- E15 invoice doc_type resolution ---')
rep = env['ir.actions.report'].search([('report_name', '=', 'vivafarm_report.viva_invoice')], limit=1)
minimal_partner = env['res.partner'].search([('name', '=', 'SO Edge Minimal')], limit=1)
if not minimal_partner:
    minimal_partner = env['res.partner'].create({
        'name': 'SO Edge Minimal', 'is_company': True, 'lang': 'en_US',
        'email': 'edge-minimal@example.invalid',
        'invoice_template_pdf_report_id': rep.id if rep else False,
    })
move = env['account.move'].create({
    'move_type': 'out_invoice', 'partner_id': minimal_partner.id,
    'invoice_date': fields.Date.today(), 'invoice_line_ids': [(0, 0, {
        'product_id': service.id, 'quantity': 1, 'price_unit': 100,
    })],
})
move._portal_ensure_token()
env.cr.commit()
url = 'http://127.0.0.1:8069/my/invoices/%d/confirm_viva' % move.id
st, hdrs, body = post(url, {
    'access_token': move.access_token, 'uploader_name': 'Min', 'confirm': '1',
}, {'upload': ('a.png', 'image/png', FILE_A)})
env.cr.commit()
rec = env['viva.signed.document'].sudo().search([
    ('move_id', '=', move.id), ('channel', '=', 'manual')], limit=1)
check('E15 invoice route ok', st in STS and loc_has(hdrs, 'upload_ok'),
      '(status=%d loc=%s)' % (st, hdrs.get('Location')))
check('E15 minimal -> tax_invoice type', bool(rec) and rec.document_type == 'tax_invoice',
      '(type=%s)' % (rec.document_type if rec else 'n/a'))

# ── Summary ──
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back)')
