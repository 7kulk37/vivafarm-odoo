#!/usr/bin/env python3
"""Slice 2 RED: Omise card flow — charge creation + transaction state.

Uses the REAL Omise sandbox API (test keys) — no mocks.
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

# ── Test: transaction returns Omise-specific processing values ──
def _processing_values():
    tx = env['payment.transaction'].create({
        'provider_id': prov.id,
        'amount': 120.0,
        'currency_id': env.ref('base.THB').id,
        'partner_id': env.ref('base.partner_root').id,
        'payment_method_id': prov.payment_method_ids.filtered(lambda m: m.code == 'card').id,
    })
    vals = tx._get_processing_values()
    assert 'omise_publishable_key' in vals, f"missing omise_publishable_key in {vals}"
    assert vals['omise_publishable_key'] == prov.omise_publishable_key, "wrong publishable key"
    assert 'return_url' in vals, f"missing return_url in {vals}"
    assert '/payment/omise/return' in vals['return_url'], f"wrong return_url: {vals['return_url']}"
test("card transaction returns omise_publishable_key + return_url", _processing_values)

# ── Test: create a real Omise token (vault API, publishable key) ──
def _create_token():
    # Same as the curl test: vault.omise.co/tokens with the PUBLIC key
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
    assert resp.status_code == 200, f"token creation failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data.get('id', '').startswith('tokn_test_'), f"unexpected token: {data}"
    assert data.get('livemode') is False, "not in test mode!"
    return data['id']
token = _create_token()
test("create real Omise test token via vault API", _create_token)

# ── Test: create a charge with the token → transaction done ──
def _charge_and_process():
    tx = env['payment.transaction'].create({
        'provider_id': prov.id,
        'amount': 120.0,
        'currency_id': env.ref('base.THB').id,
        'partner_id': env.ref('base.partner_root').id,
        'payment_method_id': prov.payment_method_ids.filtered(lambda m: m.code == 'card').id,
    })
    charge = tx._omise_create_charge(token)
    assert charge, "charge creation failed"
    assert charge.get('status') == 'successful', f"charge not successful: {charge.get('status')} {charge.get('failure_message')}"
    assert charge.get('amount') == 12000, f"wrong amount in satang: {charge.get('amount')}"
    assert charge.get('currency') == 'THB', f"wrong currency: {charge.get('currency')}"

    tx._process('omise', {'reference': tx.reference, 'omise_charge': charge})
    assert tx.state == 'done', f"transaction not done: {tx.state}"
    assert tx.provider_reference == charge.get('id'), "provider_reference not set"
test("create charge via Omise API and process to done", _charge_and_process)

# ── Test: declined card → transaction error ──
def _declined_card():
    # Create a token for a declined card (4111 1111 1114 0011 = insufficient_fund)
    resp = requests.post(
        'https://vault.omise.co/tokens',
        data={
            'card[name]': 'Test Customer',
            'card[number]': '4111111111140011',
            'card[expiration_month]': '12',
            'card[expiration_year]': '2027',
            'card[security_code]': '123',
        },
        auth=(prov.omise_publishable_key, ''),
        timeout=30,
    )
    assert resp.status_code == 200, f"token creation failed: {resp.status_code}"
    declined_token = resp.json()['id']

    tx = env['payment.transaction'].create({
        'provider_id': prov.id,
        'amount': 120.0,
        'currency_id': env.ref('base.THB').id,
        'partner_id': env.ref('base.partner_root').id,
        'payment_method_id': prov.payment_method_ids.filtered(lambda m: m.code == 'card').id,
    })
    charge = tx._omise_create_charge(declined_token)
    assert charge, "charge creation failed"
    assert charge.get('status') == 'failed', f"expected failed, got {charge.get('status')}"

    tx._process('omise', {'reference': tx.reference, 'omise_charge': charge})
    assert tx.state == 'error', f"transaction not error: {tx.state}"
test("declined card → transaction error", _declined_card)

# ── Summary ──
if errors:
    print(f"RESULT: {errors} test(s) FAILED")
    sys.exit(1)
else:
    print("RESULT: ALL TESTS PASSED")
