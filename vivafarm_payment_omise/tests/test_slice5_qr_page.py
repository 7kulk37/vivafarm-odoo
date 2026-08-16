#!/usr/bin/env python3
"""Slice 5 RED: Omise PromptPay QR on the status page.

The customer selects PromptPay → tx created → charge pending → the status
page must render the QR image so the customer can scan it with their bank app.
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

# ── Test: PromptPay tx stores QR URL + status page template renders it ──
def _qr_on_status_page():
    # Create a real PromptPay source + charge (pending)
    resp = requests.post(
        'https://api.omise.co/sources',
        data={'type': 'promptpay', 'amount': 12000, 'currency': 'THB'},
        auth=(prov.omise_secret_key, ''),
        timeout=30,
    )
    source_id = resp.json()['id']

    tx = env['payment.transaction'].create({
        'provider_id': prov.id,
        'amount': 120.0,
        'currency_id': env.ref('base.THB').id,
        'partner_id': env.ref('base.partner_root').id,
        'payment_method_id': prov.payment_method_ids.filtered(lambda m: m.code == 'promptpay').id,
    })
    charge = tx._omise_create_promptpay_charge(source_id)
    assert charge and charge.get('status') == 'pending', f"charge not pending: {charge}"
    tx._process('omise', {'reference': tx.reference, 'omise_charge': charge})
    assert tx.state == 'pending', f"tx not pending: {tx.state}"
    assert tx.omise_qr_url, "omise_qr_url not set"
    assert tx.omise_qr_url.startswith('https://'), f"bad omise_qr_url: {tx.omise_qr_url}"

    # The status page template must render the QR for pending Omise txs.
    # Check the template exists and references omise_qr_url.
    template = env.ref('vivafarm_payment_omise.omise_state_header', raise_if_not_found=False)
    assert template, "omise_state_header template not found"
    arch = template.arch_db
    assert 'omise_qr_url' in arch, "template does not reference omise_qr_url"
    assert 'img' in arch, "template does not render an img"
test("PromptPay tx stores QR URL + status page renders it", _qr_on_status_page)

# ── Test: QR download URL is fetchable (signed S3 URL) ──
def _qr_fetchable():
    # Reuse the last tx's QR URL
    tx = env['payment.transaction'].search([
        ('provider_code', '=', 'omise'),
        ('omise_qr_url', '!=', False),
    ], order='id desc', limit=1)
    assert tx, "no tx with omise_qr_url"
    resp = requests.get(tx.omise_qr_url, timeout=30)
    assert resp.status_code == 200, f"QR fetch failed: {resp.status_code}"
    assert resp.headers.get('Content-Type', '').startswith('image/'), \
        f"QR not an image: {resp.headers.get('Content-Type')}"
    assert len(resp.content) > 1000, f"QR too small: {len(resp.content)} bytes"
test("QR download URL is fetchable (image)", _qr_fetchable)

# ── Summary ──
if errors:
    print(f"RESULT: {errors} test(s) FAILED")
    sys.exit(1)
else:
    print("RESULT: ALL TESTS PASSED")
