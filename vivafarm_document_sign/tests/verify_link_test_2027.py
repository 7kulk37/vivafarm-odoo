#!/usr/bin/env python3
"""verify_link_test — Document Verification page linked-document rows.

User bug (2026-08-21): the tax invoice (ใบกำกับภาษี) 3 copied showed "-"
for BOTH Previous and Next Linked Document on the /v/<token> verification
page. Root causes (probed on staging):
  1. The verify controller only branched on document_type == 'invoice';
     tax-invoice signed docs (document_type 'tax_invoice', v164 minimal
     flow AND the tax copy of standard-flow invoices) fell into the else
     branch — both rows stayed empty.
  2. The invoice -> payment-receipt NEXT lookup used move.payment_ids
     (One2many of payments whose journal-entry move is this move —
     ALWAYS empty for reconciled invoices); the correct field is
     reconciled_payment_ids.

Checks (full SO -> DN -> tax invoice -> payment receipt chain, then the
shared-branch regression):
  L1  Tax invoice Previous = signed Delivery Note (preferred)
  L2  Tax invoice Previous falls back to the signed SO when no DN
  L3  Tax invoice Next = signed Payment Receipt (reconciled_payment_ids)
  L4  Payment Receipt Previous = the signed Tax Invoice it paid
  L5  Payment Receipt Next = '-' (nothing after a receipt)
  L6  Standard-flow Invoice (document_type 'invoice') resolves on the
      shared ('invoice','tax_invoice') branch (no crash, correct doc)
  L7  Verify page (HTTP GET) for the tax invoice renders the linked DN +
      receipt rows (end-to-end through the deployed controller)
"""
import base64
import json
import urllib.request

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


def http_get(url, headers=None):
    req = urllib.request.Request(url, method='GET')
    req.add_header('Host', 'test_sign.stg.vivafarm')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode()


def link_dict(signed):
    """Same shape as the controller's _link_dict (for direct assertions)."""
    if not signed:
        return {}
    return {
        'document_number': signed.document_number,
        'verification_code': signed.verification_code,
        'url': '/v/%s' % signed.verification_token,
    }


# The controller methods need a request env — replicate their exact logic
# here against the model so the test can run inside odoo shell.
def prev_linked(signed):
    Model = env['viva.signed.document'].sudo()
    if signed.document_type == 'delivery_note' and signed.sale_order_id:
        prev = Model.search([
            ('sale_order_id', '=', signed.sale_order_id.id),
            ('document_type', '=', 'sale_order'),
        ], limit=1)
    elif signed.document_type in ('invoice', 'tax_invoice') and signed.move_id:
        so = signed.move_id.line_ids.mapped('sale_line_ids.order_id')[:1]
        prev = None
        if so:
            prev = Model.search([
                ('sale_order_id', '=', so.id),
                ('document_type', '=', 'delivery_note'),
            ], limit=1)
            if not prev:
                prev = Model.search([
                    ('sale_order_id', '=', so.id),
                    ('document_type', '=', 'sale_order'),
                ], limit=1)
    elif signed.document_type == 'payment_receipt' and signed.payment_id:
        inv = signed.payment_id.reconciled_invoice_ids[:1]
        prev = None
        if inv:
            prev = Model.search([
                ('move_id', '=', inv.id),
                ('document_type', 'in', ('invoice', 'tax_invoice')),
            ], limit=1)
    else:
        prev = None
    return link_dict(prev)


def next_linked(signed):
    Model = env['viva.signed.document'].sudo()
    if signed.document_type == 'sale_order' and signed.sale_order_id:
        nxt = Model.search([
            ('sale_order_id', '=', signed.sale_order_id.id),
            ('document_type', '=', 'delivery_note'),
        ], limit=1)
        if not nxt:
            invs = signed.sale_order_id.invoice_ids
            if invs:
                nxt = Model.search([
                    ('move_id', 'in', invs.ids),
                    ('document_type', 'in', ('invoice', 'tax_invoice')),
                ], limit=1)
    elif signed.document_type == 'delivery_note' and signed.sale_order_id:
        invs = signed.sale_order_id.invoice_ids
        nxt = None
        if invs:
            nxt = Model.search([
                ('move_id', 'in', invs.ids),
                ('document_type', 'in', ('invoice', 'tax_invoice')),
            ], limit=1)
    elif signed.document_type in ('invoice', 'tax_invoice') and signed.move_id:
        pays = signed.move_id.reconciled_payment_ids
        nxt = None
        if pays:
            nxt = Model.search([
                ('payment_id', 'in', pays.ids),
                ('document_type', '=', 'payment_receipt'),
            ], limit=1)
    else:
        nxt = None
    return link_dict(nxt)


print('=== verify_link_test — verification page linked documents ===')

Model = env['viva.signed.document'].sudo()

# ── Setup: chain partner + product + pricelist ──
partner = env['res.partner'].search([('name', '=', 'new sign customer (tax)')], limit=1)
if not partner:
    partner = env['res.partner'].create({
        'name': 'new sign customer (tax)', 'is_company': True, 'lang': 'en_US',
    })
    rep = env['ir.actions.report'].search(
        [('report_name', '=', 'vivafarm_report.viva_invoice')], limit=1)
    if rep:
        partner.write({'invoice_template_pdf_report_id': rep.id})

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
if not product.property_account_income_id:
    income = env['account.account'].search([('account_type', '=', 'income')], limit=1)
    product.write({'property_account_income_id': income.id})
pricelist = env['product.pricelist'].search([], limit=1)

# ── 1. SO + portal accept (signs the SO) ──
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
so.write({
    'signature': SIGNATURE_B64,
    'signed_by': 'Link Test Customer',
    'signed_position': 'Manager',
})
so.action_confirm()
so_signed = env['viva.signed.document'].search(
    [('sale_order_id', '=', so.id), ('document_type', '=', 'sale_order')], limit=1)
check('SETUP SO signed doc created', bool(so_signed), '(so=%s)' % so.name)

# ── 2. Delivery note: ready -> ship & send -> customer-sign (complete + hash) ──
for line in so.order_line:
    wh = env['stock.warehouse'].search([], limit=1)
    stock_loc = wh.lot_stock_id if wh else env.ref('stock.stock_location_stock')
    env['stock.quant']._update_available_quantity(line.product_id, stock_loc, 1000)
picking = so.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
picking.move_ids._action_assign()
picking.invalidate_recordset()
picking.action_ship_and_send_dn()
env.cr.commit()
picking = env['stock.picking'].browse(picking.id)
picking.invalidate_recordset()
# The portal route writes these then calls _complete_delivery + hash
picking.write({
    'signature': SIGNATURE_B64,
    'signed_by': 'DN Receiver',
    'signed_position': 'Store Manager',
})
picking._complete_delivery()
picking.with_context(delivery_include_signature=True)._hash_delivery_accepted()
dn_signed = env['viva.signed.document'].search(
    [('picking_id', '=', picking.id), ('document_type', '=', 'delivery_note')], limit=1)
check('SETUP DN signed doc created', bool(dn_signed), '(dn=%s)' % picking.name)

# ── 3. Tax invoice created FROM the SO (so the invoice line links back) ──
inv = so._create_invoices()
inv.action_post()
inv.write({
    'signature': SIGNATURE_B64,
    'signed_by': 'Tax Sign Customer',
    'signed_position': 'Manager',
})
inv.with_context(invoice_include_signature=True)._hash_invoice_accepted()
tax_signed = env['viva.signed.document'].search(
    [('move_id', '=', inv.id), ('document_type', '=', 'tax_invoice')], limit=1)
check('SETUP tax invoice signed doc created', bool(tax_signed), '(inv=%s)' % inv.name)
if tax_signed:
    so_from_lines = inv.line_ids.mapped('sale_line_ids.order_id')[:1]
    check('SETUP invoice links back to the SO', so_from_lines.id == so.id,
          '(so=%s)' % so_from_lines.id)

# ── L1: tax invoice -> Previous = signed Delivery Note (preferred) ──
prev_tax = prev_linked(tax_signed)
check('L1 tax invoice previous = signed DN',
      prev_tax.get('document_number') == dn_signed.document_number,
      '(got=%s)' % prev_tax.get('document_number'))

# ── L2: tax invoice -> Previous falls back to the SO when no DN ──
# The product invoices on DELIVERED quantities by default; so2 has no
# delivery (that's the point of the fallback test). qty_to_invoice is
# COMPUTED at confirm time, so the policy must be 'order' BEFORE the SO
# is created — writing it afterwards leaves qty_to_invoice = 0.0 in the
# session (verified by probe 2026-08-21).
product.write({'invoice_policy': 'order'})
so2 = env['sale.order'].create({
    'partner_id': partner.id,
    'pricelist_id': pricelist.id,
    'order_line': [(0, 0, {
        'product_id': product.id,
        'product_uom_qty': 1,
        'price_unit': 50,
    })],
})
so2._portal_ensure_token()
so2.write({
    'signature': SIGNATURE_B64,
    'signed_by': 'Link Test Customer',
    'signed_position': 'Manager',
})
so2.action_confirm()
so2_signed = Model.search(
    [('sale_order_id', '=', so2.id), ('document_type', '=', 'sale_order')], limit=1)
inv2 = so2._create_invoices()
inv2.action_post()
inv2.write({
    'signature': SIGNATURE_B64,
    'signed_by': 'Tax Sign Customer',
    'signed_position': 'Manager',
})
inv2.with_context(invoice_include_signature=True)._hash_invoice_accepted()
tax2_signed = Model.search(
    [('move_id', '=', inv2.id), ('document_type', '=', 'tax_invoice')], limit=1)
if tax2_signed and so2_signed:
    prev_tax2 = prev_linked(tax2_signed)
    check('L2 tax invoice previous = SO when no DN',
          prev_tax2.get('document_number') == so2_signed.document_number,
          '(got=%s)' % prev_tax2.get('document_number'))
else:
    check('L2 tax invoice previous = SO when no DN', False,
          '(tax2=%s so2=%s)' % (bool(tax2_signed), bool(so2_signed)))

# ── L3: tax invoice -> Next = payment receipt (reconciled_payment_ids) ──
# Pay via a real payment.transaction (Omise test provider) so the payment
# is posted + reconciled + the receipt hook fires (same as production).
prov = env['payment.provider'].search([('code', '=', 'omise')], limit=1)
check('L3a Omise provider present', bool(prov))
if prov:
    tx = env['payment.transaction'].create({
        'provider_id': prov.id,
        'reference': inv.name,
        'amount': inv.amount_total,
        'currency_id': inv.currency_id.id,
        'partner_id': partner.id,
        'operation': 'online_direct',
        'state': 'done',
        'payment_method_id': prov.payment_method_ids[:1].id,
        'invoice_ids': [(4, inv.id)],
    })
    if not tx.is_post_processed:
        tx._post_process()
    payment = tx.payment_id
    check('L3b payment created + reconciled', bool(payment)
          and inv.id in payment.reconciled_invoice_ids.ids,
          '(pay=%s rec=%s)' % (payment.id if payment else None,
                               payment.reconciled_invoice_ids.ids if payment else []))
    if payment:
        receipt = Model.search([
            ('payment_id', '=', payment.id),
            ('document_type', '=', 'payment_receipt'),
        ], limit=1)
        check('L3c receipt signed doc created', bool(receipt),
              '(pay=%s)' % payment.name)
        if receipt:
            nxt_tax = next_linked(tax_signed)
            check('L3d tax invoice next = payment receipt',
                  nxt_tax.get('document_number') == receipt.document_number,
                  '(got=%s)' % nxt_tax.get('document_number'))

            # ── L4: payment receipt -> Previous = the tax invoice ──
            prev_rec = prev_linked(receipt)
            check('L4 receipt previous = tax invoice',
                  prev_rec.get('document_number') == tax_signed.document_number,
                  '(got=%s)' % prev_rec.get('document_number'))

            # ── L5: receipt has no Next ──
            nxt_rec = next_linked(receipt)
            check('L5 receipt next empty', not nxt_rec, '(got=%s)' % nxt_rec)

            # ── L7: end-to-end HTTP verify page for the tax invoice ──
            # The HTTP worker is a separate process — it cannot see the
            # shell session's uncommitted records. Commit the chain first,
            # then re-browse.
            env.cr.commit()
            tax_signed.invalidate_recordset()
            dn_signed.invalidate_recordset()
            receipt.invalidate_recordset()
            try:
                html = http_get('http://127.0.0.1:8069/v/%s' % tax_signed.verification_token)
                check('L7 verify page renders', 'Document Verification' in html,
                      '(len=%d)' % len(html))
                check('L7 page links Previous DN',
                      dn_signed.document_number in html,
                      '(expect %s)' % dn_signed.document_number)
                check('L7 page links Next receipt',
                      receipt.document_number in html,
                      '(expect %s)' % receipt.document_number)
                check('L7 no bare dash on Previous row',
                      'Previous Linked Document</dt><dd>-</dd>' not in html)
                check('L7 no bare dash on Next row',
                      'Next Linked Document</dt><dd>-</dd>' not in html)
            except Exception as e:
                check('L7 verify page', False, '(error: %s)' % repr(e)[:150])

# ── L5b/L6: standard-flow plain invoice resolves on the shared branch ──
std = env['res.partner'].search([('name', '=', 'SO Sign Test Customer')], limit=1)
if std:
    inv_std = env['account.move'].create({
        'move_type': 'out_invoice',
        'partner_id': std.id,
        'invoice_line_ids': [(0, 0, {
            'product_id': product.id,
            'quantity': 1,
            'price_unit': 100,
        })],
    })
    inv_std.action_post()
    inv_std.write({
        'signature': SIGNATURE_B64,
        'signed_by': 'Standard Acknowledger',
        'signed_position': 'Manager',
    })
    inv_std.with_context(invoice_include_signature=True)._hash_invoice_accepted()
    inv_std_signed = Model.search(
        [('move_id', '=', inv_std.id), ('document_type', '=', 'invoice')], limit=1)
    check('L6a standard invoice signed', bool(inv_std_signed))
    if inv_std_signed:
        # Direct invoice (no SO, no payment) -> both links empty, no crash
        prev_std = prev_linked(inv_std_signed)
        check('L6b standard invoice prev = {} (shared branch, no crash)',
              not prev_std, '(got=%s)' % prev_std)
        nxt_std = next_linked(inv_std_signed)
        check('L6c standard invoice next = {} (no payments)',
              not nxt_std, '(got=%s)' % nxt_std)
else:
    check('L6 standard partner', False, '(missing)')

# ── Summary ──
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
print('(rolled back — committed HTTP-test records stay for manual inspection)')
