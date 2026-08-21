#!/usr/bin/env python3
"""manual_upload_flow_test — standard flow AND minimal flow end-to-end
(2026-08-21, after the edge-test bug fixes v22 / report v167).

Standard flow: partner has NO invoice_template_pdf_report_id → manual uploads
seal document_type='invoice' (ใบแจ้งหนี้ plain).
Minimal flow: partner HAS invoice_template_pdf_report_id = tax invoice →
manual uploads seal document_type='tax_invoice' (ใบกำกับภาษี).

Checks:
  F1  Standard partner invoice manual upload -> document_type='invoice'
  F2  Standard helper _get_manual_signed_document() resolves it (plain branch)
  F3  Minimal partner invoice manual upload -> document_type='tax_invoice'
  F4  Minimal helper _get_manual_signed_document() resolves it (tax branch)
  F5  The two records do NOT cross-contaminate (each has its own doc_type)
  F6  Both verify pages render the MANUAL UPLOAD badge + uploader + disclaimer
  F7  Invoice route still returns upload_ok for BOTH (no 500 on posted moves)
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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post(url, fields_dict, files):
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


def get_manual(record_id):
    return env['viva.signed.document'].sudo().search([
        ('odoo_model', '=', 'account.move'),
        ('odoo_record_id', '=', record_id),
        ('channel', '=', 'manual'),
    ], limit=1)


print('=== manual_upload_flow_test — standard flow AND minimal flow ===')

env.cr.rollback()  # clean slate from any prior session

# ── Setup: partners + products ──
standard = env['res.partner'].search([('name', '=', 'FLOW Standard Partner')], limit=1)
if not standard:
    standard = env['res.partner'].create({
        'name': 'FLOW Standard Partner', 'is_company': True, 'lang': 'en_US',
        'email': 'flow-standard@example.invalid',
    })
# Minimal partner: invoice_template_pdf_report_id -> the Viva TAX invoice report
tax_rep = env['ir.actions.report'].search([('report_name', '=', 'vivafarm_report.viva_invoice')], limit=1)
minimal = env['res.partner'].search([('name', '=', 'FLOW Minimal Partner')], limit=1)
if not minimal:
    minimal = env['res.partner'].create({
        'name': 'FLOW Minimal Partner', 'is_company': True, 'lang': 'en_US',
        'email': 'flow-minimal@example.invalid',
        'invoice_template_pdf_report_id': tax_rep.id if tax_rep else False,
    })
service = env['product.product'].search([('name', '=', 'FLOW Service Product')], limit=1)
if not service:
    service = env['product.product'].create({'name': 'FLOW Service Product', 'type': 'service', 'sale_ok': True})
    income = env['account.account'].search([('account_type', '=', 'income')], limit=1)
    service.write({'property_account_income_id': income.id})
pricelist = env['product.pricelist'].search([], limit=1)

check('setup tax report resolved', bool(tax_rep),
      '(id=%s)' % (tax_rep.id if tax_rep else 'n/a'))


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


def upload_manual(move):
    """POST the hand-signed copy; returns (status, headers)."""
    url = 'http://127.0.0.1:8069/my/invoices/%d/confirm_viva' % move.id
    st, hdrs, body = post(url, {
        'access_token': move.access_token, 'uploader_name': 'Flow Guy', 'confirm': '1',
    }, {'upload': ('flow.png', 'image/png', PNG)})
    return st, hdrs


# ── F1/F2: standard flow ──
print('--- F1/F2 standard flow (document_type=invoice) ---')
inv_std = make_invoice(standard)
env.cr.commit()
st, hdrs = upload_manual(inv_std)
env.cr.commit()
inv_std.invalidate_recordset()
rec_std = get_manual(inv_std.id)
check('F1 standard upload_ok', st in STS and loc_has(hdrs, 'upload_ok'),
      '(status=%d loc=%s)' % (st, hdrs.get('Location')))
check('F1 standard -> document_type=invoice', bool(rec_std) and rec_std.document_type == 'invoice',
      '(type=%s)' % (rec_std.document_type if rec_std else 'n/a'))
check('F2 standard helper resolves it', bool(inv_std._get_manual_signed_document()),
      '(rec=%s)' % (inv_std._get_manual_signed_document().id if inv_std._get_manual_signed_document() else 'n/a'))

# ── F3/F4: minimal flow ──
print('--- F3/F4 minimal flow (document_type=tax_invoice) ---')
inv_min = make_invoice(minimal)
env.cr.commit()
st, hdrs = upload_manual(inv_min)
env.cr.commit()
inv_min.invalidate_recordset()
rec_min = get_manual(inv_min.id)
check('F3 minimal upload_ok', st in STS and loc_has(hdrs, 'upload_ok'),
      '(status=%d loc=%s)' % (st, hdrs.get('Location')))
check('F3 minimal invoice_type=tax_invoice', bool(rec_min) and rec_min.document_type == 'tax_invoice',
      '(type=%s)' % (rec_min.document_type if rec_min else 'n/a'))
check('F4 minimal helper resolves it', bool(inv_min._get_manual_signed_document()),
      '(rec=%s)' % (inv_min._get_manual_signed_document().id if inv_min._get_manual_signed_document() else 'n/a'))

# ── F5: no cross-contamination ──
print('--- F5 no cross-contamination ---')
check('F5 standard helper does NOT return the minimal record',
      not inv_std._get_manual_signed_document().filtered(lambda r: r.id == (rec_min.id if rec_min else -1)))
check('F5 minimal helper does NOT return the standard record',
      not inv_min._get_manual_signed_document().filtered(lambda r: r.id == (rec_std.id if rec_std else -1)))
check('F5 distinct records', bool(rec_std) and bool(rec_min) and rec_std.id != rec_min.id,
      '(std=%s min=%s)' % (rec_std.id if rec_std else 'n/a', rec_min.id if rec_min else 'n/a'))

def verify_get(token):
    req = urllib.request.Request('http://127.0.0.1:8069/v/%s' % token,
                                 headers={'Host': 'test_sign.stg.vivafarm'})
    return urllib.request.urlopen(req, timeout=30).read().decode()


print('--- F6 verify pages ---')
if rec_std:
    html_std = verify_get(rec_std.verification_token)
    check('F6 standard verify page MANUAL UPLOAD', 'MANUAL UPLOAD' in html_std)
    check('F6 standard verify uploader shown', 'Flow Guy' in html_std)
    check('F6 standard disclaimer', 'does not constitute authentication' in html_std)
if rec_min:
    html_min = verify_get(rec_min.verification_token)
    check('F6 minimal verify page MANUAL UPLOAD', 'MANUAL UPLOAD' in html_min)
    check('F6 minimal verify uploader shown', 'Flow Guy' in html_min)
    check('F6 minimal disclaimer', 'does not constitute authentication' in html_min)

# ── F7: draft invoice upload (the bug the edge suite caught) ──
print('--- F7 draft invoice upload (E15 regression) ---')
draft = env['account.move'].create({
    'move_type': 'out_invoice', 'partner_id': standard.id,
    'invoice_date': fields.Date.today(), 'invoice_line_ids': [(0, 0, {
        'product_id': service.id, 'quantity': 1, 'price_unit': 20,
    })],
})
draft._portal_ensure_token()
env.cr.commit()
st, hdrs = upload_manual(draft)
env.cr.commit()
check('F7 draft invoice upload_ok (no 500)', st in STS and loc_has(hdrs, 'upload_ok'),
      '(status=%d loc=%s)' % (st, hdrs.get('Location')))

print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back)')
