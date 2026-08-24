#!/usr/bin/env python3
"""receipt_idempotency_test_2027 — RED test: payment_receipt race convergence.

Review defect #1 (2026-08-24): the Omise webhook and the 2-min rescue cron
can both call _create_payment -> _hash_payment_receipt for the SAME payment.
The other three seal paths (SO/DN/invoice) converge on UNIQUE constraints;
the receipt path had only a soft pre-check search, so a race could create
TWO payment_receipt records for one payment.

Checks:
  R1  Partial UNIQUE index exists on (payment_id) WHERE document_type =
      'payment_receipt' (the DB-layer guard).
  R2  _hash_payment_receipt is idempotent: calling it twice on the same
      payment returns the SAME record (soft pre-check path).
  R3  The DB constraint actually rejects a second payment_receipt row for
      the same payment (simulated race — direct create must raise
      IntegrityError, proving the guard is physical, not just a search).
  R4  A manual payment_slip upload on the same payment does NOT collide
      with the receipt (partial index scoping).
"""
import base64

from odoo import fields
from psycopg2 import IntegrityError

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


print('=== receipt_idempotency_test — payment_receipt race convergence ===')

# ── Setup: a posted customer invoice + a real payment (Omise test provider) ──
partner = env['res.partner'].search([('name', '=', 'receipt race customer')], limit=1)
if not partner:
    partner = env['res.partner'].create({
        'name': 'receipt race customer', 'is_company': True, 'lang': 'en_US',
    })
product = env['product.product'].search([('name', '=', 'Receipt Race Product')], limit=1)
if not product:
    goods_cat = env['product.category'].search([], limit=1)
    product = env['product.product'].create({
        'name': 'Receipt Race Product',
        'type': 'consu',
        'sale_ok': True,
        'categ_id': goods_cat.id,
        'is_storable': True,
    })
if not product.property_account_income_id:
    income = env['account.account'].search([('account_type', '=', 'income')], limit=1)
    product.write({'property_account_income_id': income.id})
# invoice_policy must be 'order' BEFORE the SO is created — qty_to_invoice
# is computed at confirm time (skill pitfall #35, verified 2026-08-21).
product.write({'invoice_policy': 'order'})
pricelist = env['product.pricelist'].search([], limit=1)

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
inv = so._create_invoices()
inv.action_post()

prov = env['payment.provider'].search([('code', '=', 'omise')], limit=1)
check('SETUP Omise provider present', bool(prov))
if not prov:
    print('  SKIP: no Omise provider — cannot build a real payment')
    print('RESULT PASS=%d FAIL=%d' % (PASS, FAIL))
    raise SystemExit(0 if FAIL == 0 else 1)

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
check('SETUP payment created', bool(payment), '(pay=%s)' % (payment.name if payment else None))
if not payment:
    print('  SKIP: no payment created')
    print('RESULT PASS=%d FAIL=%d' % (PASS, FAIL))
    raise SystemExit(0 if FAIL == 0 else 1)

# ── R1: partial unique index exists ──
env.cr.execute("""
    SELECT indexname FROM pg_indexes
    WHERE tablename = 'viva_signed_document'
      AND indexname = 'viva_signed_document_payment_unique_partial'
""")
check('R1 partial UNIQUE(payment_id) index exists', bool(env.cr.fetchone()))

# ── R2: idempotent — second call returns the SAME record ──
first = payment._hash_payment_receipt()
second = payment._hash_payment_receipt()
check('R2 double-call returns same record', first.id == second.id,
      '(first=%s second=%s)' % (first.id, second.id))
count = env['viva.signed.document'].search_count([
    ('payment_id', '=', payment.id),
    ('document_type', '=', 'payment_receipt'),
])
check('R2 exactly one payment_receipt record', count == 1, '(count=%s)' % count)

# ── R3: DB constraint physically rejects a second receipt row ──
rejected = False
try:
    with env.cr.savepoint():
        env['viva.signed.document'].create({
            'document_number': payment.name,
            'document_type': 'payment_receipt',
            'odoo_model': 'account.payment',
            'odoo_record_id': payment.id,
            'payment_id': payment.id,
            'revision': 1,
            'signed_at': fields.Datetime.now(),
        })
except IntegrityError:
    rejected = True
check('R3 duplicate receipt create raises IntegrityError', rejected)

# ── R4: manual payment_slip on the same payment does NOT collide ──
slip = env['viva.signed.document'].create({
    'document_number': payment.name,
    'document_type': 'payment_slip',
    'channel': 'manual',
    'odoo_model': 'account.payment',
    'odoo_record_id': payment.id,
    'payment_id': payment.id,
    'revision': 1,
    'signer_name': 'Race Test Uploader',
    'signed_at': fields.Datetime.now(),
})
check('R4 manual payment_slip coexists with receipt', bool(slip.id),
      '(slip=%s)' % slip.id)

print('RESULT PASS=%d FAIL=%d' % (PASS, FAIL))
raise SystemExit(0 if FAIL == 0 else 1)
