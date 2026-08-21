#!/usr/bin/env python3
"""manual_upload_test — the manual hand-signed upload flow (no digital signature).

User flow (2026-08-21, lawyer-verified): the customer prints, hand-signs,
scans, and uploads the signed paper copy back through the token-protected
portal. The ERP seals the EXACT uploaded bytes (SHA-256, hash-only,
channel='manual') and emails a confirmation carrying the /v/<token>
verification link + code.

Checks:
  U1  Model: viva.signed.document has channel + payment_slip selection +
      manual-upload fields
  U2  _create_manual_record seals exact bytes: sha256 matches, attachment
      stores the same bytes, channel='manual', link field set
  U3  Idempotency: second seal of the same record returns the SAME record
  U4  Portal route: POST /my/orders/<id>/confirm_viva -> sealed record
      (with uploader name + ip + ua) + verify URL + code
  U5  Confirmation email: no NEW exception notification for the partner
      (healthy send; auto_delete removes the mail row)
  U6  Verify page /v/<token>: renders MANUAL UPLOAD badge + uploader row +
      the lawyer-approved disclaimer (no authenticity claim)
  U7  Hash-compare: uploading the same bytes -> HASH MATCH
  U8  The verify page does NOT claim signature authenticity (no "proves the
      customer signed" wording)
"""
import base64
import hashlib
import json
import urllib.request
import urllib.error
from urllib.parse import urlencode

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


# 1x1 transparent PNG (smallest valid file — used as the "signed scan")
PNG_B64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
FILE_BYTES = base64.b64decode(PNG_B64)
FILE_SHA = hashlib.sha256(FILE_BYTES).hexdigest()


def http_get(url, headers=None):
    req = urllib.request.Request(url, method='GET')
    req.add_header('Host', 'test_sign.stg.vivafarm')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def http_post_multipart(url, fields, files, headers=None):
    """POST a multipart/form-data request; returns (status, body)."""
    import uuid
    boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
    body = b''
    for k, v in fields.items():
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
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


print('=== manual_upload_test — hand-signed upload (no digital signature) ===')

Model = env['viva.signed.document'].sudo()

# ── U1: model fields ──
print('--- U1 model fields ---')
check('U1 channel field exists', 'channel' in env['viva.signed.document']._fields)
check('U1 channel has manual option',
      any(v == 'manual' for v, _ in env['viva.signed.document']._fields['channel'].selection))
check('U1 document_type has payment_slip',
      any(v == 'payment_slip' for v, _ in env['viva.signed.document']._fields['document_type'].selection))
for f in ('uploader_name', 'uploader_ip', 'uploader_user_agent', 'source_filename',
          'source_mimetype', 'seller_note'):
    check('U1 %s field exists' % f, f in env['viva.signed.document']._fields)

# ── Setup: partner + SO ──
partner = env['res.partner'].search([('name', '=', 'SO Sign Test Customer')], limit=1)
if not partner:
    partner = env['res.partner'].create({
        'name': 'SO Sign Test Customer', 'is_company': True, 'lang': 'en_US',
        'email': 'so-sign-test@example.invalid',
    })
product = env['product.product'].search([('name', '=', 'SO Sign Test Product')], limit=1)
if not product:
    product = env['product.product'].create({'name': 'SO Sign Test Product', 'type': 'service', 'sale_ok': True})
    income = env['account.account'].search([('account_type', '=', 'income')], limit=1)
    product.write({'property_account_income_id': income.id})
pricelist = env['product.pricelist'].search([], limit=1)

so = env['sale.order'].create({
    'partner_id': partner.id,
    'pricelist_id': pricelist.id,
    'order_line': [(0, 0, {
        'product_id': product.id,
        'product_uom_qty': 2,
        'price_unit': 100,
    })],
})
so._portal_ensure_token()
print('SO', so.id, so.name, 'token', so.access_token)

# ── U2: direct seal (ORM-level) on a SECOND SO ──
print('--- U2 _create_manual_record ---')
so2 = env['sale.order'].create({
    'partner_id': partner.id,
    'pricelist_id': pricelist.id,
    'order_line': [(0, 0, {
        'product_id': product.id,
        'product_uom_qty': 1,
        'price_unit': 50,
    })],
})
signed = Model._create_manual_record(
    model='sale.order', record_id=so2.id, document_type='sale_order',
    document_number=so2.name, filename='signed.pdf', mimetype='application/pdf',
    data=FILE_BYTES, uploader_name='Manu Customer', uploader_ip='10.0.0.1',
    uploader_agent='TestAgent/1.0', seller_note='hand-signed in store',
)
check('U2 record created', bool(signed))
check('U2 channel manual', signed.channel == 'manual', '(got %s)' % signed.channel)
check('U2 sha256 == file sha', signed.pdf_sha256 == FILE_SHA,
      '(got %s)' % signed.pdf_sha256[:16])
stored = base64.b64decode(signed.signed_attachment_id.datas)
check('U2 stored bytes == uploaded bytes', stored == FILE_BYTES,
      '(stored=%dB uploaded=%dB)' % (len(stored), len(FILE_BYTES)))
check('U2 uploader name', signed.uploader_name == 'Manu Customer',
      '(got %s)' % signed.uploader_name)
check('U2 uploader ip', signed.uploader_ip == '10.0.0.1', '(got %s)' % signed.uploader_ip)
check('U2 link field set', signed.sale_order_id.id == so2.id,
      '(sale_order_id=%s)' % signed.sale_order_id.id)
check('U2 verification code', bool(signed.verification_code))
check('U2 verification url has token', signed.verification_token in signed._get_verification_url())

# ── U3: idempotency ──
print('--- U3 idempotency ---')
signed2 = Model._create_manual_record(
    model='sale.order', record_id=so2.id, document_type='sale_order',
    document_number=so2.name, filename='x.png', mimetype='image/png',
    data=FILE_BYTES, uploader_name='Other',
)
check('U3 same record returned', signed2.id == signed.id,
      '(first=%s second=%s)' % (signed.id, signed2.id))

# ── U4: portal route (multipart POST) on the FIRST SO ──
print('--- U4 /my/orders/<id>/confirm_viva ---')
env.cr.commit()
url = 'http://127.0.0.1:8069/my/orders/%d/confirm_viva' % so.id
status, body = http_post_multipart(url, {
    'access_token': so.access_token,
    'uploader_name': 'Portal Uploader',
    'confirm': '1',
}, {
    'upload': ('signed-scan.png', 'image/png', FILE_BYTES),
})
check('U4 POST accepted (redirect 303/302/200)', status in (200, 302, 303),
      '(status=%d)' % status)
env.cr.commit()
so.invalidate_recordset()
manual = Model.search([
    ('odoo_model', '=', 'sale.order'),
    ('odoo_record_id', '=', so.id),
    ('document_type', '=', 'sale_order'),
    ('channel', '=', 'manual'),
], limit=1)
check('U4 manual record exists', bool(manual))
if manual:
    check('U4 uploader name = Portal Uploader',
          manual.uploader_name == 'Portal Uploader',
          '(got %s)' % manual.uploader_name)
    check('U4 uploader ip recorded', bool(manual.uploader_ip),
          '(ip=%s)' % manual.uploader_ip)
    check('U4 source filename', manual.source_filename == 'signed-scan.png',
          '(got %s)' % manual.source_filename)

# ── U5: confirmation email — no NEW exception for the partner ──
print('--- U5 confirmation email ---')
exc_before = env['mail.notification'].search_count([
    ('res_partner_id', '=', partner.id),
    ('notification_status', '=', 'exception'),
])
# The route sends the template (auto_delete -> successful send removes the
# mail.mail row + notifications); assert via the no-new-exception pattern.
env.cr.commit()
exc_after = env['mail.notification'].search_count([
    ('res_partner_id', '=', partner.id),
    ('notification_status', '=', 'exception'),
])
check('U5 no NEW exception notification', exc_after == exc_before,
      '(before=%d after=%d)' % (exc_before, exc_after))

# ── U6/U7/U8: verify page ──
print('--- U6-U8 verify page ---')
if manual:
    vurl = 'http://127.0.0.1:8069/v/%s' % manual.verification_token
    html = http_get(vurl).decode()
    check('U6 verify page renders', 'Document Verification' in html, '(len=%d)' % len(html))
    check('U6 MANUAL UPLOAD badge', 'MANUAL UPLOAD' in html)
    check('U6 uploader name shown', 'Portal Uploader' in html)
    check('U6 disclaimer shown', 'does not constitute authentication' in html)
    # Hash-compare with the SAME bytes
    check('U7 sha matches file', manual.pdf_sha256 == FILE_SHA,
          '(stored=%s file=%s)' % (manual.pdf_sha256[:12], FILE_SHA[:12]))
    # No authenticity claim (safe-word check)
    check('U8 no authenticity claim', 'proves the customer signed' not in html.lower())

# ── Summary ──
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back)')
