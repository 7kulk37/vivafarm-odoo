#!/usr/bin/env python3
"""evidence_guard_test — L1 regression: a signed record with no evidence
must never claim 'SIGNED / VALID'.

Audit L1 (2026-08-29): one record (SO/2026/00016) reached state='signed'
with NEITHER pdf_sha256 NOR signed_attachment_id, and its /v/<token> page
wrongly claimed 'SIGNED / VALID'. docsign v25 added _has_evidence() + a
write() guard + the 'SIGNED — INSUFFICIENT EVIDENCE' verify-page state.
This test locks that invariant so it cannot silently regress.

Run on test_sign:
    sudo -u odoo odoo shell -d test_sign --no-http \
      --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/opt/odoo-custom-addons \
      < evidence_guard_test_2027.py

Checks:
  E1  _has_evidence() False for a signed record with no evidence
  E2  _has_evidence() True once hash + attachment are written
  E3  write() guard blocks clearing the evidence pair on a signed record
  E4  verify page renders 'SIGNED — INSUFFICIENT EVIDENCE' (never 'SIGNED / VALID')
  E5  verify page shows the disclaimer for the evidence-less record
"""
import base64
import os
import hashlib
import urllib.request

from odoo.exceptions import UserError

TEST_HOST = os.environ.get('VIVAFARM_TEST_HOST', TEST_HOST)

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


def http_get(url):
    req = urllib.request.Request(url, method='GET')
    req.add_header('Host', TEST_HOST)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode()


Model = env['viva.signed.document']

# ── E1/E2: _has_evidence() ──
# A bare record: state defaults to 'signed' but no evidence legs are set.
bare = Model.create({
    'document_type': 'tax_invoice',
    'document_number': 'EVIDENCE-GUARD-TEST',
})
check('E1 _has_evidence False for bare signed record', bare._has_evidence() is False)
check('E1b state defaults to signed', bare.state == 'signed')

# Write the two evidence legs -> _has_evidence() flips True.
png_b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
data = base64.b64decode(png_b64)
att = env['ir.attachment'].create({
    'name': 'evidence_guard_test.pdf',
    'datas': base64.b64encode(data),
    'res_model': 'viva.signed.document',
    'res_id': bare.id,
    'type': 'binary',
})
bare.write({'pdf_sha256': hashlib.sha256(data).hexdigest(),
            'signed_attachment_id': att.id})
check('E2 _has_evidence True after hash+attachment', bare._has_evidence() is True)

# ── E3: write() guard ──
try:
    bare.write({'pdf_sha256': False})
    check('E3 write guard blocks clearing hash', False)
except UserError:
    check('E3 write guard blocks clearing hash', True)
try:
    bare.write({'signed_attachment_id': False})
    check('E3b write guard blocks clearing attachment', False)
except UserError:
    check('E3b write guard blocks clearing attachment', True)

# ── E4/E5: verify page for a DIFFERENT bare record (no evidence) ──
# The HTTP worker is a separate process — commit first so it can see the
# record (same pattern as verify_link_test / manual_upload_test).
bare2 = Model.create({
    'document_type': 'tax_invoice',
    'document_number': 'EVIDENCE-GUARD-TEST-2',
})
env.cr.commit()
bare2.invalidate_recordset()
html = http_get('http://127.0.0.1:8069/v/%s' % bare2.verification_token)
check('E4 verify page renders', 'Document Verification' in html, '(len=%d)' % len(html))
check('E4b shows INSUFFICIENT EVIDENCE', 'SIGNED — INSUFFICIENT EVIDENCE' in html)
check('E4c does NOT show SIGNED / VALID', 'SIGNED / VALID' not in html)
check('E5 disclaimer shown', 'missing from the archive' in html)

print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back — uncommitted test data discarded)')
