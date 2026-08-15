#!/usr/bin/env python3
"""sign_test — end-to-end function test for vivafarm_document_sign.

Run against test_sign (or any Thai-chart DB with vivafarm_report +
vivafarm_document_sign installed):

    sudo -u odoo odoo shell -d test_sign --no-http \
      --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/opt/odoo-custom-addons \
      < sign_test_2027.py

Checks:
  S1  Signing service: sha256 stable, RSA sig, cert metadata (migration seam)
  S2  Wizard evidence: hash + cert shown before signing
  S3  Sign flow: creates signed document, hash recorded, attachment matches
  S4  Lock: edit blocked, button_draft blocked at ORM level
  S5  Reissue: new move with same date → Rev 2, previous_hash chains
  S6  Revoke: state + audit preserved
  S7  QR + verification URL: opaque token, no record IDs, no hash in QR
"""
import base64
import hashlib
import sys

from odoo.exceptions import UserError

PASS = 0
FAIL = 0


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  ✅ %s %s' % (name, detail))
    else:
        FAIL += 1
        print('  ❌ %s %s' % (name, detail))


def setup_partner_product():
    partner = env['res.partner'].search([('name', '=', 'Sign Test Customer')], limit=1)
    if not partner:
        partner = env['res.partner'].create({'name': 'Sign Test Customer', 'is_company': True})
    income = env['account.account'].search([('account_type', '=', 'income')], limit=1)
    product = env['product.product'].search([('name', '=', 'Sign Test Product')], limit=1)
    if not product:
        product = env['product.product'].create({
            'name': 'Sign Test Product', 'type': 'service', 'sale_ok': True,
            'property_account_income_id': income.id,
        })
    journal = env['account.journal'].search([('type', '=', 'sale')], limit=1)
    return partner, product, journal


def make_invoice(partner, product, journal, qty=2, price=100, date='2026-08-15',
                 reissue_root=None):
    inv = env['account.move'].create({
        'move_type': 'out_invoice',
        'partner_id': partner.id,
        'journal_id': journal.id,
        'invoice_date': date,
        'reissue_root_id': reissue_root.id if reissue_root else False,
        'invoice_line_ids': [(0, 0, {
            'name': 'Sign Test Product', 'product_id': product.id,
            'quantity': qty, 'price_unit': price, 'tax_ids': [],
        })],
    })
    inv.action_post()
    return inv


print('=== sign_test — vivafarm_document_sign function test ===')

partner, product, journal = setup_partner_product()

# ── S1 Signing service ──
print('--- S1 Signing service ---')
from odoo.addons.vivafarm_document_sign.services.signing_service import (
    SigningService, sha256_hex)

service = SigningService(env)
from odoo.addons.vivafarm_document_sign.services.signing_service import FileKeyBackend
check('S1 backend is file (PoC)', isinstance(service.backend, FileKeyBackend))
pdf_bytes = b'%PDF-1.4 sign-test bytes'
check('S1 sha256 64 hex', len(sha256_hex(pdf_bytes)) == 64)
sig_b64, cert_info, signed_at = service.sign_pdf(pdf_bytes)
check('S1 signature base64', isinstance(sig_b64, str) and len(sig_b64) > 100)
check('S1 cert subject', 'VivaFarm Test Signer' in cert_info['subject'])
check('S1 cert issuer', 'VivaFarm Test Root CA' in cert_info['issuer'])
check('S1 cert fingerprint 64 hex', len(cert_info['fingerprint']) == 64)
pub_pem = service.backend.public_key_pem()
check('S1 verify original', service.verify_signature(pdf_bytes, sig_b64, pub_pem) is True)
check('S1 verify tampered rejected',
      service.verify_signature(pdf_bytes.replace(b'sign', b'Sign'), sig_b64, pub_pem) is False)

# ── S2 Wizard evidence ──
print('--- S2 Wizard evidence ---')
inv = make_invoice(partner, product, journal)
wiz = env['viva.sign.wizard'].create({'move_id': inv.id})
wiz.compute_evidence()
check('S2 wizard hash shown', len(wiz.pdf_sha256) == 64)
check('S2 wizard cert shown', 'VivaFarm Test Signer' in wiz.certificate_subject)
check('S2 wizard type TEST', 'TEST' in wiz.certificate_type)

# ── S3 Sign flow ──
print('--- S3 Sign flow ---')
result = wiz.action_sign()
check('S3 action is reload', result.get('type') == 'ir.actions.client'
      and result.get('tag') == 'reload')
signed = env['viva.signed.document'].search([('move_id', '=', inv.id)], limit=1)
check('S3 signed doc created', bool(signed))
check('S3 document number', signed.document_number == inv.name)
check('S3 revision 1', signed.revision == 1)
check('S3 hash recorded', len(signed.pdf_sha256) == 64)
check('S3 signature stored', len(signed.signature_b64) > 100)
check('S3 token set', len(signed.verification_token) >= 20)
check('S3 attachment stored', bool(signed.signed_attachment_id))
att_bytes = base64.b64decode(signed.signed_attachment_id.datas)
check('S3 attachment hash matches',
      hashlib.sha256(att_bytes).hexdigest() == signed.pdf_sha256)
check('S3 audit SIGNED event',
      len(env['viva.document.audit'].search([('document_id', '=', signed.id),
                                             ('event', '=', 'SIGNED')])) == 1)

# ── S4 Lock ──
print('--- S4 Lock ---')
try:
    inv.write({'payment_reference': 'HACK'})
    check('S4 edit blocked', False)
except UserError:
    check('S4 edit blocked', True)
try:
    inv.button_draft()
    check('S4 reset-to-draft blocked', False)
except UserError:
    check('S4 reset-to-draft blocked', True)

# ── S5 Reissue (ป.86/2542 ข้อ 25) ──
print('--- S5 Reissue chain ---')
inv2 = make_invoice(partner, product, journal, reissue_root=inv)
wiz2 = env['viva.sign.wizard'].create({'move_id': inv2.id})
r2 = wiz2.action_sign()
signed2 = env['viva.signed.document'].search([('move_id', '=', inv2.id)], limit=1)
check('S5 reissue posted', inv2.name != inv.name and inv2.state == 'posted')
check('S5 rev2 revision', signed2.revision == 2)
check('S5 rev2 previous hash', signed2.previous_document_hash == signed.pdf_sha256)
try:
    inv.write({'payment_reference': 'LATE'})
    check('S5 original still locked after reissue', False)
except UserError:
    check('S5 original still locked after reissue', True)

# ── S6 Revoke ──
print('--- S6 Revoke ---')
signed.action_revoke('function-test revoke')
check('S6 state revoked', signed.state == 'revoked')
check('S6 reason recorded', signed.revocation_reason == 'function-test revoke')
check('S6 revoke audit',
      len(env['viva.document.audit'].search([('document_id', '=', signed.id),
                                             ('event', '=', 'REVOKED')])) == 1)
try:
    signed.action_revoke('again')
    check('S6 re-revoke blocked', False)
except UserError:
    check('S6 re-revoke blocked', True)

# ── S7 QR + verification URL ──
print('--- S7 QR + verification URL ---')
url = signed2._get_verification_url()
check('S7 URL has token', signed2.verification_token in url)
check('S7 URL no record id', str(signed2.id) not in url and str(signed2.move_id.id) not in url)
check('S7 URL no hash', signed2.pdf_sha256 not in url)
qr = signed2._qr_data_uri()
check('S7 QR is png data uri', qr.startswith('data:image/png;base64,'))
check('S7 QR not empty', len(qr) > 500)

# ── Audit append-only ──
print('--- S8 Audit append-only ---')
try:
    env['viva.document.audit'].search([('document_id', '=', signed.id)]).unlink()
    check('S8 audit unlink blocked', False)
except UserError:
    check('S8 audit unlink blocked', True)

print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back — no test data left in DB)')
sys.exit(1 if FAIL else 0)
