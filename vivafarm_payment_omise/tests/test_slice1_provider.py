#!/usr/bin/env python3
"""Slice 1 RED: Omise provider exists with code, keys, and payment methods."""
import sys

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

# ── Test: provider record exists with code 'omise' ──
def _provider_exists():
    prov = env['payment.provider'].search([('code', '=', 'omise')], limit=1)
    assert prov, "no payment.provider with code='omise'"
    assert prov.state in ('test', 'enabled', 'disabled'), f"unexpected state {prov.state}"
test("provider with code='omise' exists", _provider_exists)

# ── Test: provider has Omise key fields ──
def _provider_has_keys():
    prov = env['payment.provider'].search([('code', '=', 'omise')], limit=1)
    assert prov, "no provider"
    assert 'omise_publishable_key' in prov._fields, "missing omise_publishable_key field"
    assert 'omise_secret_key' in prov._fields, "missing omise_secret_key field"
    assert 'omise_webhook_secret' in prov._fields, "missing omise_webhook_secret field"
test("provider has omise_publishable_key/secret_key/webhook_secret fields", _provider_has_keys)

# ── Test: provider supports card + promptpay methods ──
def _provider_supports_methods():
    prov = env['payment.provider'].search([('code', '=', 'omise')], limit=1)
    assert prov, "no provider"
    codes = prov.payment_method_ids.mapped('code')
    assert 'card' in codes, f"card not in supported methods: {codes}"
    assert 'promptpay' in codes, f"promptpay not in supported methods: {codes}"
test("provider supports card + promptpay payment methods", _provider_supports_methods)

# ── Test: promptpay method is active (not the inactive catalog stub) ──
def _promptpay_active():
    prov = env['payment.provider'].search([('code', '=', 'omise')], limit=1)
    assert prov, "no provider"
    pm = prov.payment_method_ids.filtered(lambda m: m.code == 'promptpay')
    assert pm, "promptpay method not linked to provider"
    assert pm.active, "promptpay method is inactive"
test("promptpay method linked to provider is active", _promptpay_active)

# ── Summary ──
if errors:
    print(f"RESULT: {errors} test(s) FAILED")
    sys.exit(1)
else:
    print("RESULT: ALL TESTS PASSED")
