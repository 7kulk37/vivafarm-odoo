#!/usr/bin/env python3
"""invoice_send_inv_e2e — end-to-end: Send INV wizard attaches the Viva Invoice PDF.

Creates a fresh posted invoice, opens the wizard with the flag, simulates the
send, and verifies the stored PDF content is the Viva Invoice (title INVOICE,
no TAX INVOICE tri-label, invoice number, 5% T&C) and the email carries it.
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
    'invoice_date': '2026-08-19',
    'invoice_line_ids': [(0, 0, {
        'name': 'Test Send INV',
        'quantity': 1,
        'price_unit': 100,
        'account_id': account.id,
    })],
})
inv.action_post()
print('INV', inv.id, inv.name)

# ── Send via wizard with the flag ──
try:
    wiz = env['account.move.send.wizard'].with_context(
        viva_invoice_report=True,
        active_model='account.move',
        active_ids=inv.ids,
    ).create({'move_id': inv.id})
    check('E1 wizard pdf_report_id = Viva Invoice',
          wiz.pdf_report_id.id == env.ref('vivafarm_report.report_viva_invoice_plain').id,
          '(got %s)' % wiz.pdf_report_id.id)
    send = env['account.move.send'].with_context(viva_invoice_report=True)
    send._generate_and_send_invoices(
        inv,
        from_cron=False,
        allow_raising=True,
        allow_fallback_pdf=False,
        sending_methods={'email': {'checked': True}},
        pdf_report=wiz.pdf_report_id,
    )
    check('E2 send completed without error', True)
    check('E3 invoice_pdf_report_file set', bool(inv.invoice_pdf_report_file))
    check('E5 is_move_sent set', inv.is_move_sent)

    # Content check on the stored PDF
    stored = base64.b64decode(inv.invoice_pdf_report_file) if inv.invoice_pdf_report_file else b''
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(stored))
    text = ''
    for page in reader.pages:
        text += (page.extract_text() or '')
    check('E4a stored PDF has INVOICE title', 'INVOICE' in text)
    check('E4b stored PDF has no TAX INVOICE tri-label', 'TAX INVOICE' not in text)
    check('E4c stored PDF has invoice number', inv.name in text)
    check('E4d stored PDF has 5% T&C', '5%' in text)

    # Email: mail.mail outgoing + comment message with attachment
    mail = env['mail.mail'].search([('model', '=', 'account.move'), ('res_id', '=', inv.id)], order='id desc', limit=1)
    check('E6 mail.mail created', bool(mail), '(none)')
    check('E6b mail state outgoing', mail.state == 'outgoing', '(got %s)' % mail.state)
    check('E7 mail has attachment', bool(mail.attachment_ids))
    if mail.attachment_ids:
        att = mail.attachment_ids[0]
        check('E8 attachment is PDF', att.mimetype == 'application/pdf', '(got %s)' % att.mimetype)
        check('E9 attachment name has Invoice prefix', att.name.startswith('Invoice -'), '(got %s)' % att.name)
    msg = inv.message_ids.filtered(lambda m: m.message_type == 'comment')
    check('E10 comment message posted', bool(msg))
except Exception as e:
    check('E1-E10 send flow', False, str(e)[:200])

# ── Cleanup ──
inv.button_draft()
inv.with_context(force_delete=True).unlink()
env.cr.rollback()

print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
