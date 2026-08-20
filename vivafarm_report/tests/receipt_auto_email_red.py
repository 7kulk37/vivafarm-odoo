#!/usr/bin/env python3
"""slice6_receipt_red — RED: portal Omise payment auto-sends the Viva receipt.

Creates a fresh posted invoice + a done Omise transaction (online_direct,
invoice linked), calls _create_payment (the exact post-process path used by
the webhook), and asserts a receipt mail.mail is created with the Viva
Payment Receipt PDF attached.

RED expectation: FAIL until the _create_payment override + template exist.
"""
import base64
import io
import re
PASS = 0
FAIL = 0

def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  PASS: %s' % name)
    else:
        FAIL += 1
        print('  FAIL: %s %s' % (name, detail))

# ── Setup: fresh posted invoice ──
partner = env['res.partner'].search([('is_company', '=', True), ('email', '!=', False)], limit=1)
product = env['product.product'].search([('sale_ok', '=', True)], limit=1)
account = env['account.account'].search([('account_type', '=', 'income')], limit=1)
journal = env['account.journal'].search([('type', '=', 'sale')], limit=1)
inv = env['account.move'].create({
    'move_type': 'out_invoice',
    'partner_id': partner.id,
    'journal_id': journal.id,
    'invoice_date': '2026-08-20',
    'invoice_line_ids': [(0, 0, {
        'name': 'Receipt Test',
        'quantity': 1,
        'price_unit': 600,
        'account_id': account.id,
    })],
})
inv.action_post()
print('INV', inv.id, inv.name)

# ── Setup: Omise provider + fake done tx ──
prov = env['payment.provider'].search([('code', '=', 'omise')], limit=1)
if not prov:
    print('SKIP: no Omise provider')
    env.cr.rollback()
    raise SystemExit(0)

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
print('TX', tx.id, tx.reference)

# ── The exact path the webhook uses after _process: _post_process → _create_payment ──
try:
    if not tx.is_post_processed:
        tx._post_process()
    payment = tx.payment_id
    check('R1 payment created', bool(payment), '(none)')
    if payment:
        check('R2 payment posted', payment.state == 'posted' or payment.state == 'paid', '(got %s)' % payment.state)
        check('R3 invoice reconciled', inv.id in payment.reconciled_invoice_ids.ids,
              '(reconciled %s)' % payment.reconciled_invoice_ids.ids)

    # Email assertion: the receipt mail must exist
    mail = env['mail.mail'].search([('model', '=', 'account.payment'), ('res_id', '=', payment.id if payment else 0)],
                                   order='id desc', limit=1)
    check('R4 receipt mail.mail created', bool(mail), '(none)')
    if mail:
        check('R5 subject = Payment receipt PBNK... (Ref INV...)',
              bool(re.match(r'^Payment receipt \S+ \(Ref %s\)$' % re.escape(inv.name), mail.subject or '')),
              '(got %s)' % mail.subject)
        check('R6 recipient = invoice partner', partner.id in mail.recipient_ids.ids, '(got %s)' % mail.recipient_ids.ids)
        check('R7 receipt PDF attached', any(a.mimetype == 'application/pdf' for a in mail.attachment_ids),
              '(attachments %s)' % [(a.name, a.mimetype) for a in mail.attachment_ids])
        for a in mail.attachment_ids:
            if a.mimetype == 'application/pdf':
                raw = base64.b64decode(a.raw) if a.raw else b''
                check('R8 attached PDF is Viva receipt (has Payment Receipt title)',
                      b'Payment Receipt' in raw or 'Payment Receipt' in (a.name or ''),
                      '(name %s len %d)' % (a.name, len(raw)))
except Exception as e:
    check('R1-R8 flow', False, str(e)[:200])

# ── Cleanup: cancel + unlink, rollback ──
env.cr.rollback()
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
