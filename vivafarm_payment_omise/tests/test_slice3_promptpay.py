#!/usr/bin/env python3
"""Slice 3 RED: Omise PromptPay flow — source + charge + QR document URL.

Uses the REAL Omise sandbox API (test keys) — no mocks.
Each test creates its own source (PromptPay sources are single-use).
"""
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

def _make_source():
    resp = requests.post(
        'https://api.omise.co/sources',
        data={'type': 'promptpay', 'amount': 12000, 'currency': 'THB'},
        auth=(prov.omise_secret_key, ''),
        timeout=30,
    )
    assert resp.status_code == 200, f"source creation failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data.get('id', '').startswith('src_test_'), f"unexpected source: {data}"
    assert data.get('type') == 'promptpay', f"wrong type: {data.get('type')}"
    return data['id']

# ── Test: create a PromptPay source via Omise API ──
def _create_source():
    source_id = _make_source()
    assert source_id, "no source id"
test("create real Omise PromptPay source via API", _create_source)

# ── Test: create a charge with the source → pending + QR document ──
def _charge_with_source():
    source_id = _make_source()  # fresh source per call (single-use)
    tx = env['payment.transaction'].create({
        'provider_id': prov.id,
        'amount': 120.0,
        'currency_id': env.ref('base.THB').id,
        'partner_id': env.ref('base.partner_root').id,
        'payment_method_id': prov.payment_method_ids.filtered(lambda m: m.code == 'promptpay').id,
    })
    charge = tx._omise_create_promptpay_charge(source_id)
    assert charge, "charge creation failed"
    assert charge.get('status') == 'pending', f"expected pending, got {charge.get('status')}"
    assert charge.get('amount') == 12000, f"wrong amount in satang: {charge.get('amount')}"
    assert charge.get('currency') == 'THB', f"wrong currency: {charge.get('currency')}"

    # The QR lives on the source's scannable_code.image.download_uri
    source = charge.get('source', {})
    scannable = source.get('scannable_code', {})
    image = scannable.get('image', {})
    qr_url = image.get('download_uri')
    assert qr_url, "no QR download_uri on source scannable_code"
    assert qr_url.startswith('https://'), f"bad QR url: {qr_url}"
    return charge
charge = _charge_with_source()
test("create PromptPay charge → pending + QR document URL", _charge_with_source)

# ── Test: transaction stores the QR URL for the pay page ──
def _tx_stores_qr():
    tx = env['payment.transaction'].create({
        'provider_id': prov.id,
        'amount': 120.0,
        'currency_id': env.ref('base.THB').id,
        'partner_id': env.ref('base.partner_root').id,
        'payment_method_id': prov.payment_method_ids.filtered(lambda m: m.code == 'promptpay').id,
    })
    tx._process('omise', {'reference': tx.reference, 'omise_charge': charge})
    assert tx.state == 'pending', f"transaction not pending: {tx.state}"
    assert tx.provider_reference == charge.get('id'), "provider_reference not set"
    assert tx.omise_qr_url, "omise_qr_url not set on transaction"
    assert tx.omise_qr_url.startswith('https://'), f"bad omise_qr_url: {tx.omise_qr_url}"
test("transaction stores omise_qr_url for the pay page", _tx_stores_qr)

# ── Summary ──
if errors:
    print(f"RESULT: {errors} test(s) FAILED")
    sys.exit(1)
else:
    print("RESULT: ALL TESTS PASSED")
