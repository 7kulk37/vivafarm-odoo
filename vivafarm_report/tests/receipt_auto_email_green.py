#!/usr/bin/env python3
"""slice6_receipt_green — GREEN: portal Omise payment triggers the receipt hook.

Intercept _send_payment_receipt_email (spy) to prove the hook fires once,
then directly call template.send_mail(force_send=False) to inspect the real
mail.mail (recipient, subject, Viva receipt PDF) — auto_delete/force_send
would delete sent mails, so the spy is the reliable assertion.
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

# ── Spy: intercept _send_payment_receipt_email to count invocations ──
PaymentTx = type(tx)
calls = []
orig = PaymentTx._send_payment_receipt_email
def spy(self, payment):
    calls.append(payment)
    # still run the real send (force_send=True + auto_delete -> mail removed)
    return orig(self, payment)
PaymentTx._send_payment_receipt_email = spy

try:
    if not tx.is_post_processed:
        tx._post_process()
    payment = tx.payment_id
    check('G1 payment created', bool(payment), '(none)')
    if payment:
        check('G2 payment posted', payment.state == 'posted' or payment.state == 'paid', '(got %s)' % payment.state)
        check('G3 invoice reconciled', inv.id in payment.reconciled_invoice_ids.ids,
              '(reconciled %s)' % payment.reconciled_invoice_ids.ids)
    check('G4 receipt send hook fired once', len(calls) == 1, '(calls %d)' % len(calls))
    if calls:
        check('G5 hook got the payment', calls[0].id == payment.id, '(got %s)' % calls[0].id)
except Exception as e:
    check('G1-G5 flow', False, str(e)[:200])

# ── Prove the mail itself is correct (force_send=False keeps the row) ──
tpl = env.ref('vivafarm_report.viva_email_template_payment_receipt', raise_if_not_found=False)
check('G6 template exists', bool(tpl))
if tpl and payment:
    mail_id = tpl.send_mail(payment.id, force_send=False, raise_exception=True)
    mail = env['mail.mail'].browse(mail_id)
    check('G7 subject = Payment receipt PBNK... (Ref INV...)',
          bool(re.match(r'^Payment receipt \S+ \(Ref %s\)$' % re.escape(inv.name), mail.subject or '')),
          '(got %s)' % mail.subject)
    check('G8 recipient = invoice partner', partner.id in mail.recipient_ids.ids, '(got %s)' % mail.recipient_ids.ids)
    check('G9 receipt PDF attached', any(a.mimetype == 'application/pdf' for a in mail.attachment_ids),
          '(attachments %s)' % [(a.name, a.mimetype) for a in mail.attachment_ids])
    for a in mail.attachment_ids:
        if a.mimetype == 'application/pdf':
            raw = a.raw or b''
            # PDF text is font-compressed; extract with pypdf like the
            # invoice_send_inv_e2e test.
            text = ''
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(raw))
                for page in reader.pages:
                    text += (page.extract_text() or '')
            except Exception:
                text = ''
            check('G10 attached PDF is Viva receipt (Payment Receipt title)',
                  'Payment Receipt' in text or 'Payment receipt' in text.lower(),
                  '(name %s len %d text_head %s)' % (a.name, len(raw), text[:60]))

# restore
PaymentTx._send_payment_receipt_email = orig
env.cr.rollback()
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
