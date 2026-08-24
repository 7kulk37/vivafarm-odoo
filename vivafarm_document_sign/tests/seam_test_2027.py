#!/usr/bin/env python3
"""seam_test_2027 — digital↔manual seal seam (review defect #2 fix).

The seam semantics (2026-08-24, refactor batch 2): ONE seal per document,
whichever channel lands first. A manual hand-signed upload that lands first
MUST block/short-circuit the digital sign path (never overwrite a manual
hash-only record with RSA signature fields); a digital sign that lands
first MUST make a later manual upload converge on the existing record
(_create_manual_record already does this).

Checks:
  S1  sale.order._sealed_document is doc-type scoped — a signed DN chained
      to the SO does NOT count as the SO's own seal (was a false positive
      _is_signed()).
  S2  Manual upload first on an SO -> _hash_customer_accepted returns the
      manual record and does NOT write RSA signature fields onto it.
  S3  _is_signed() respects the seam: manual seal makes the SO signed, and
      the record stays channel='manual' (no digital overwrite).
  S4  invoice seam: manual tax_invoice seal first -> _hash_invoice_accepted
      returns it untouched (no signature_b64).
  S5  Wizard seam: action_sign on an invoice with an existing manual seal
      raises UserError (no silent overwrite).
"""
import base64

from odoo import fields
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

print('=== seam_test — one seal per doc, digital↔manual seam ===')

Model = env['viva.signed.document'].sudo()

# ── Setup: partner + product (invoice_policy 'order' BEFORE SO create) ──
partner = env['res.partner'].search([('name', '=', 'seam test customer')], limit=1)
if not partner:
    partner = env['res.partner'].create({
        'name': 'seam test customer', 'is_company': True, 'lang': 'en_US',
    })
product = env['product.product'].search([('name', '=', 'Seam Test Product')], limit=1)
if not product:
    goods_cat = env['product.category'].search([], limit=1)
    product = env['product.product'].create({
        'name': 'Seam Test Product',
        'type': 'consu',
        'sale_ok': True,
        'categ_id': goods_cat.id,
        'is_storable': True,
    })
if not product.property_account_income_id:
    income = env['account.account'].search([('account_type', '=', 'income')], limit=1)
    product.write({'property_account_income_id': income.id})
product.write({'invoice_policy': 'order'})
pricelist = env['product.pricelist'].search([], limit=1)

# ── S1: SO._sealed_document is doc-type scoped ──
so = env['sale.order'].create({
    'partner_id': partner.id,
    'pricelist_id': pricelist.id,
    'order_line': [(0, 0, {
        'product_id': product.id,
        'product_uom_qty': 1,
        'price_unit': 100,
    })],
})
so.action_confirm()
# Deliver + DN sign (chained to the SO) — the DN record carries sale_order_id
for line in so.order_line:
    wh = env['stock.warehouse'].search([], limit=1)
    stock_loc = wh.lot_stock_id if wh else env.ref('stock.stock_location_stock')
    env['stock.quant']._update_available_quantity(line.product_id, stock_loc, 1000)
picking = so.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
picking.move_ids._action_assign()
picking.invalidate_recordset()
picking.write({
    'signature': SIGNATURE_B64,
    'signed_by': 'Seam DN Receiver',
    'signed_position': 'Store Manager',
})
picking.with_context(delivery_include_signature=True)._hash_delivery_accepted()
dn_signed = Model.search(
    [('picking_id', '=', picking.id), ('document_type', '=', 'delivery_note')], limit=1)
check('S1a DN signed (chain link exists)', bool(dn_signed), '(dn=%s)' % (dn_signed.document_number if dn_signed else None))
# The SO's OWN seal is still absent — the DN chain link does NOT count
check('S1b SO._sealed_document NOT the DN', bool(so._sealed_document()) is False,
      '(found=%s)' % (so._sealed_document().document_type if so._sealed_document() else ''))
check('S1c SO._is_signed False with only DN', so._is_signed() is False)

# ── S2+S3: manual FIRST -> digital hash short-circuits ──
manual = Model._create_manual_record(
    model='sale.order',
    record_id=so.id,
    document_type='sale_order',
    document_number=so.name,
    filename='signed_so.pdf',
    mimetype='application/pdf',
    data=b'%PDF-1.4 fake manual upload bytes',
    uploader_name='Seam Uploader',
    uploader_ip='192.0.2.1',
)
check('S2a manual seal created', bool(manual) and manual.channel == 'manual',
      '(ch=%s)' % (manual.channel if manual else ''))
so.invalidate_recordset()
# Now the digital sign path — must short-circuit, NOT overwrite with RSA
so.write({'signature': SIGNATURE_B64, 'signed_by': 'Seam Buyer', 'signed_position': 'Manager'})
returned = so._hash_customer_accepted()
check('S2b digital hash returns the manual record', returned.id == manual.id,
      '(returned=%s manual=%s)' % (returned.id, manual.id))
manual.invalidate_recordset()
check('S2c manual record NOT overwritten (no RSA)', bool(manual.signature_b64) is False,
      '(sig=%s)' % (bool(manual.signature_b64)))
check('S3 _is_signed True (manual counts)', so._is_signed() is True)

# ── S4: invoice seam — manual first, then _hash_invoice_accepted ──
so2 = env['sale.order'].create({
    'partner_id': partner.id,
    'pricelist_id': pricelist.id,
    'order_line': [(0, 0, {
        'product_id': product.id,
        'product_uom_qty': 1,
        'price_unit': 50,
    })],
})
so2.action_confirm()
inv2 = so2._create_invoices()
inv2.action_post()
manual_inv = Model._create_manual_record(
    model='account.move',
    record_id=inv2.id,
    document_type='invoice',
    document_number=inv2.name,
    filename='signed_inv.pdf',
    mimetype='application/pdf',
    data=b'%PDF-1.4 fake manual invoice',
    uploader_name='Seam Uploader',
)
inv2.write({'signature': SIGNATURE_B64, 'signed_by': 'Seam Buyer', 'signed_position': 'Manager'})
inv2.invalidate_recordset()
returned_inv = inv2.with_context(invoice_include_signature=True)._hash_invoice_accepted()
check('S4 invoice digital returns manual record', returned_inv.id == manual_inv.id,
      '(returned=%s manual=%s)' % (returned_inv.id, manual_inv.id))
manual_inv.invalidate_recordset()
check('S4 invoice manual NOT overwritten by RSA', bool(manual_inv.signature_b64) is False)

# ── S5: wizard seam — refuses to sign a manually-sealed invoice ──
wiz = env['viva.sign.wizard'].create({'move_id': inv2.id})
try:
    wiz.action_sign()
    check('S5 wizard refused manual seal', False, '(no UserError raised)')
except UserError:
    check('S5 wizard refused manual seal', True, '(UserError raised)')

print('RESULT PASS=%d FAIL=%d' % (PASS, FAIL))
raise SystemExit(0 if FAIL == 0 else 1)
