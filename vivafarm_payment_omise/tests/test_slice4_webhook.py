#!/usr/bin/env python3
"""Slice 4 RED: Omise webhook — signature verification + charge.complete → done.

Uses the REAL Omise sandbox API (test keys) — no mocks.
"""
import base64
import hashlib
import hmac
import json
import sys

import requests

errors = 0

def test(name, fn):
    global errors
    try:
        fn()
        print(f"  PASS: {name}")
    except AssertionError as e:
        print(f"  FAIL: {name} — {e}")
        errors += 1
    except Exception as e:
        print(f"  FAIL: {name} — unexpected: {e}")
        errors += 1

# ── Setup: find the Omise provider ──
prov = env['payment.provider'].search([('code', '=', 'omise')], limit=1)
if not prov:
    print("SKIP: no Omise provider")
    sys.exit(0)

# ── Test: webhook signature verification (HMAC-SHA256, base64 secret) ──
def _verify_signature():
    # Per Omise docs: signed payload = "{timestamp}.{raw_body}", secret is base64-decoded
    secret = base64.b64encode(b'test-webhook-secret-1234567890').decode()
    timestamp = '1758696391'
    body = json.dumps({'key': 'value'}).encode()

    # Compute the expected signature the way Omise would
    signed_payload = f"{timestamp}.".encode() + body
    expected = hmac.new(base64.b64decode(secret), signed_payload, hashlib.sha256).hexdigest()

    # Verify via the controller's pure static method
    from odoo.addons.vivafarm_payment_omise.controllers.main import OmiseController
    result = OmiseController._verify_webhook_signature_with_secret(
        secret, expected, timestamp, body
    )
    assert result is True, f"signature verification failed: {result}"

    # Wrong signature must fail
    bad = OmiseController._verify_webhook_signature_with_secret(
        secret, '0' * 64, timestamp, body
    )
    assert bad is False, "wrong signature accepted!"
test("webhook signature verification (HMAC-SHA256, base64 secret)", _verify_signature)

# ── Test: charge.complete webhook → transaction done ──
def _webhook_complete():
    # Create a real card token (card charges complete synchronously to 'successful')
    resp = requests.post(
        'https://vault.omise.co/tokens',
        data={
            'card[name]': 'Test Customer',
            'card[number]': '4242424242424242',
            'card[expiration_month]': '12',
            'card[expiration_year]': '2027',
            'card[security_code]': '123',
        },
        auth=(prov.omise_publishable_key, ''),
        timeout=30,
    )
    assert resp.status_code == 200, f"token creation failed: {resp.status_code}"
    token = resp.json()['id']

    tx = env['payment.transaction'].create({
        'provider_id': prov.id,
        'amount': 120.0,
        'currency_id': env.ref('base.THB').id,
        'partner_id': 19,  # Test Sign Customer — has receivable account set
        'payment_method_id': prov.payment_method_ids.filtered(lambda m: m.code == 'card').id,
    })
    charge = tx._omise_create_charge(token)
    assert charge and charge.get('status') == 'successful', f"charge not successful: {charge}"
    tx._process('omise', {'reference': tx.reference, 'omise_charge': charge})
    assert tx.state == 'done', f"tx not done: {tx.state}"

    # Simulate the webhook: charge.complete event with the charge ID.
    # The model method fetches the charge independently, sets the tx done,
    # and post-processes synchronously (payment created immediately).
    env['payment.transaction']._omise_process_webhook_event({
        'object': 'event',
        'id': 'evt_test_webhook',
        'key': 'charge.complete',
        'data': {'id': charge['id']},
    })
    tx.invalidate_recordset()
    assert tx.state == 'done', f"tx not done after webhook: {tx.state}"
    assert tx.is_post_processed, "tx not post-processed after webhook"
    assert tx.payment_id, "payment not created synchronously by webhook"
    assert tx.payment_id.state in ('in_process', 'paid'), f"payment not posted: {tx.payment_id.state}"
test("charge.complete webhook → transaction done + payment posted synchronously", _webhook_complete)

# ── Summary ──
if errors:
    print(f"RESULT: {errors} test(s) FAILED")
    sys.exit(1)
else:
    print("RESULT: ALL TESTS PASSED")
