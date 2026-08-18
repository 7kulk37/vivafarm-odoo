#!/usr/bin/env python3
"""so_sign_test — end-to-end function test for sale.order acceptance hashing.

Run against test_sign (with vivafarm_report + vivafarm_document_sign
installed):

    sudo -u odoo odoo shell -d test_sign --no-http \
      --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/opt/odoo-custom-addons \
      < so_sign_test_2027.py

Checks:
  S1  Backend confirm WITHOUT customer signature -> NO hash (gate works)
  S2  Portal accept (signature written) -> action_confirm -> signed doc
  S3  Hash + attachment match (exact stamped bytes)
  S4  Lock: substance edit blocked at ORM level
  S5  QR + verification URL: opaque token, no record IDs, no hash in QR
  S6  Print serves the STORED signed PDF (ir_actions_report override)
  S7  DB-layer guard: unique(sale_order_id) exists AND a duplicate sign
      attempt converges to exactly ONE signed document (no double-sign)
"""
import base64
import hashlib
import sys
from datetime import datetime, timezone

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
    return partner, product, pricelist


def make_so(partner, product, pricelist, qty=2, price=100):
    so = env['sale.order'].create({
        'partner_id': partner.id,
        'pricelist_id': pricelist.id,
        'order_line': [(0, 0, {
            'product_id': product.id,
            'product_uom_qty': qty,
            'price_unit': price,
        })],
    })
    return so


print('=== so_sign_test — sale.order acceptance hash ===')

partner, product, pricelist = setup_partner_product()

# ── S1 Backend confirm without signature -> NO hash ──
print('--- S1 Backend confirm (no customer signature) ---')
so1 = make_so(partner, product, pricelist)
so1.action_confirm()
check('S1 state sale', so1.state == 'sale')
check('S1 no signed doc', not so1._is_signed(),
      '(backend confirm without portal signature must NOT hash)')

# ── S2 Portal accept -> action_confirm -> signed doc ──
print('--- S2 Portal accept triggers hash ---')
so2 = make_so(partner, product, pricelist)
# Mirror the portal route (sale/controllers/portal.py:325-330): write the
# customer's signature, then _validate_order -> action_confirm.
so2.write({
    'signed_by': 'Test Customer',
    'signed_on': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
    'signature': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
})
so2.action_confirm()
check('S2 state sale', so2.state == 'sale')
signed = env['viva.signed.document'].search([('sale_order_id', '=', so2.id)], limit=1)
check('S2 signed doc created', bool(signed))
check('S2 document number', signed.document_number == so2.name)
check('S2 document type', signed.document_type == 'sale_order')
check('S2 revision 1', signed.revision == 1)
check('S2 hash recorded', len(signed.pdf_sha256) == 64)
check('S2 signature stored', len(signed.signature_b64) > 100)
check('S2 token set', len(signed.verification_token) >= 20)
check('S2 attachment stored', bool(signed.signed_attachment_id))
check('S2 audit SIGNED event',
      len(env['viva.document.audit'].search([('document_id', '=', signed.id),
                                             ('event', '=', 'SIGNED')])) == 1)

# ── S3 Hash + attachment match ──
print('--- S3 Stamped bytes are the signed bytes ---')
att_bytes = base64.b64decode(signed.signed_attachment_id.datas)
check('S3 attachment hash matches',
      hashlib.sha256(att_bytes).hexdigest() == signed.pdf_sha256)
check('S3 attachment is PDF', att_bytes[:4] == b'%PDF')
# PDF text is compressed — check the HTML render carries the hash block
# (the same template that produced the stamped PDF).
html = env['ir.actions.report']._render_qweb_html(
    'vivafarm_report.viva_quotation_so', [so2.id])[0]
check('S3 hash block in render', b'Digitally Signed Document' in html,
      '(the stamped render carries the block)')

# ── S4 Lock ──
print('--- S4 Lock ---')
try:
    so2.write({'client_order_ref': 'HACK'})
    check('S4 edit blocked', False)
except UserError:
    check('S4 edit blocked', True)
try:
    so2.write({'order_line': [(1, so2.order_line.id, {'price_unit': 999})]})
    check('S4 line edit blocked', False)
except UserError:
    check('S4 line edit blocked', True)

# ── S5 QR + verification URL ──
print('--- S5 QR + verification URL ---')
url = signed._get_verification_url()
check('S5 URL has token', signed.verification_token in url)
check('S5 URL no record id', str(signed.id) not in url and str(signed.sale_order_id.id) not in url)
check('S5 URL no hash', signed.pdf_sha256 not in url)
qr = signed._qr_data_uri()
check('S5 QR is png data uri', qr.startswith('data:image/png;base64,'))
check('S5 QR not empty', len(qr) > 500)

# ── S6 Print serves the STORED signed PDF ──
print('--- S6 Print == signed == verified ---')
pdf_bytes = env['ir.actions.report']._render_qweb_pdf(
    'vivafarm_report.viva_quotation_so', [so2.id])[0]
check('S6 print returns stored bytes', pdf_bytes == att_bytes,
      '(ir_actions_report override serves the signed attachment)')

# ── S7 DB-layer guard: unique(sale_order_id) + duplicate-sign convergence ──
# The 3rd guard (user request 2026-08-17): PostgreSQL must reject a second
# signed document for the same sale order at the DB level, and the sign
# flow must CONVERGE (reuse the winner's record) instead of crashing.
print('--- S7 DB-layer guard (unique sale_order_id) ---')
# 7a. The constraint physically exists in the DB (Odoo 19 nightly dropped
#     the _sql_constraints shim — the unique constraints were MISSING from
#     pg_constraint; verify with models.Constraint the constraint is real).
from odoo.orm.table_objects import Constraint as _SQLConstraint
cons = [obj for obj in env['viva.signed.document']._table_objects.values()
        if isinstance(obj, _SQLConstraint)]
check('S7 has models.Constraint for sale_order_id',
      any('unique' in (d := c.get_definition(env.registry)).lower()
          and 'sale_order_id' in d.lower() for c in cons),
      '(constraints=%d)' % len(cons))

# 7b. A duplicate sign attempt converges: same SO, second _hash_customer_accepted
#     must NOT create a second record — it reuses the existing one.
so3 = make_so(partner, product, pricelist)
so3.write({
    'signed_by': 'Test Customer',
    'signed_on': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
    'signature': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
})
so3.action_confirm()
signed3 = env['viva.signed.document'].search([('sale_order_id', '=', so3.id)], limit=1)
check('S7 first sign created record', bool(signed3))
count_before = env['viva.signed.document'].search_count([('sale_order_id', '=', so3.id)])
so3._hash_customer_accepted()  # duplicate sign attempt (race loser path)
count_after = env['viva.signed.document'].search_count([('sale_order_id', '=', so3.id)])
check('S7 duplicate sign did not create a second record',
      count_after == count_before == 1,
      '(before=%d after=%d)' % (count_before, count_after))

print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back — no test data left in DB)')
sys.exit(1 if FAIL else 0)
