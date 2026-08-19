#!/usr/bin/env python3
"""invoice_hash_test_2027 — RED test: _hash_invoice_accepted + document_type 'invoice' + stamp + stored-bytes.

Asserts:
  H1  account.move._hash_invoice_accepted exists
  H2  viva.signed.document document_type has 'invoice' option
  H3  _hash_invoice_accepted creates a signed document with document_type='invoice'
  H4  signed document has pdf_sha256 + signature_b64 + signed_attachment_id
  H5  signed document has signer_name from signed_by
  H6  _is_signed() returns True after hashing
  H7  ir_actions_report serves STORED bytes for viva_invoice_plain when signed
  H8  invoice stamp template exists (viva_invoice_plain_document_sign_stamp)
  H9  buyer signature renders in the plain invoice under invoice_include_signature
"""
import base64
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

# ── Setup: a posted customer invoice ──
inv = env['account.move'].search([
    ('move_type', '=', 'out_invoice'),
    ('state', '=', 'posted'),
    ('name', '!=', '/'),
    ('signature', '=', False),
], order='id desc', limit=1)
print('INV', inv.id, inv.name)

# ── H1: method exists ──
check('H1 _hash_invoice_accepted exists',
      hasattr(env['account.move'], '_hash_invoice_accepted'))

# ── H2: document_type has invoice ──
try:
    sel = env['viva.signed.document']._fields['document_type'].selection
    check('H2 document_type has invoice', any(v == 'invoice' for v, _l in sel),
          '(got %s)' % [v for v, _l in sel])
except Exception as e:
    check('H2 document_type has invoice', False, str(e)[:120])

# ── H3-H6: hash the invoice ──
try:
    # 1x1 red pixel PNG (base64 — fields.Image requires base64)
    png_b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
    inv.write({
        'signed_by': 'Test Acknowledger',
        'signed_position': 'Manager',
        'signed_on': '2026-08-19 10:00:00',
        'signature': png_b64,
    })
    inv.with_context(invoice_include_signature=True)._hash_invoice_accepted()
    signed = env['viva.signed.document'].search([('move_id', '=', inv.id)], limit=1)
    check('H3 signed doc created', bool(signed))
    check('H3b document_type invoice', signed.document_type == 'invoice', '(got %s)' % signed.document_type)
    check('H3c document_number = invoice name', signed.document_number == inv.name, '(got %s)' % signed.document_number)
    check('H4a pdf_sha256 set', bool(signed.pdf_sha256))
    check('H4b signature_b64 set', bool(signed.signature_b64))
    check('H4c signed_attachment_id set', bool(signed.signed_attachment_id))
    check('H5 signer_name from signed_by', signed.signer_name == 'Test Acknowledger', '(got %s)' % signed.signer_name)
    check('H6 _is_signed True', inv._is_signed())
except Exception as e:
    check('H3-H6 hash flow', False, str(e)[:200])

# ── H7: stored bytes served ──
try:
    stored = base64.b64decode(signed.signed_attachment_id.datas)
    served = env['ir.actions.report']._render_qweb_pdf(
        'vivafarm_report.viva_invoice_plain', [inv.id])[0]
    check('H7 stored bytes served', served == stored,
          '(served %d vs stored %d)' % (len(served), len(stored)))
except Exception as e:
    check('H7 stored bytes served', False, str(e)[:120])

# ── H8: stamp template exists ──
try:
    tpl = env.ref('vivafarm_document_sign.viva_invoice_plain_document_sign_stamp')
    check('H8 stamp template exists', True)
    check('H8b stamp has Digitally Signed', 'Digitally Signed' in tpl.arch or 'เอกสารลงลายมือชื่อดิจิทัล' in tpl.arch)
except Exception as e:
    check('H8 stamp template exists', False, str(e)[:120])

# ── H9: buyer signature renders under context ──
try:
    html = env['ir.actions.report'].with_context(
        invoice_include_signature=True)._render_qweb_html(
            'vivafarm_report.viva_invoice_plain', [inv.id])[0].decode('utf-8')
    check('H9 html renders', True)
    check('H9b has Test Acknowledger', 'Test Acknowledger' in html)
    check('H9c has Manager position', 'Manager' in html)
except Exception as e:
    check('H9 buyer signature renders', False, str(e)[:120])

# ── Summary ──
print('')
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
env.cr.rollback()
