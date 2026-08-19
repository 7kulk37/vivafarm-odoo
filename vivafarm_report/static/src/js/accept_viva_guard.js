/**
 * vivafarm_report — client-side one-shot guard for Accept & Sign forms.
 *
 * Why (bug 2 follow-up, 2026-08-17): the stock portal.signature_form already
 * disables its submit button while the RPC is in flight (addLoadingEffect),
 * but closing and reopening the modal re-mounts the component with a fresh,
 * enabled button — so the same page can fire a second POST. The server-side
 * idempotency check (controllers/portal.py) turns any second POST into a
 * benign sign_ok, and this file adds the customer-side second guard the
 * user asked for: the button cannot be spammed while the server is working.
 *
 * Handles BOTH signature-form families that can coexist on one order page:
 *   - #accept_viva            — SO quotation acceptance (/accept_viva)
 *   - #accept_viva_delivery_<id> — delivery note receipt acknowledgment
 *                               (/my/picking/<id>/accept_viva)
 *
 * The lock is page-lifetime per form: after the FIRST submit attempt the
 * submit button stays locked and the modal can no longer be re-opened, even
 * after the component re-mounts. A reload re-renders the page server-side —
 * if the document was already signed the button is not rendered at all.
 */
(function () {
    'use strict';

    function isVivaForm(el) {
        if (!el || el.nodeType !== 1) {
            return false;
        }
        if (el.id === 'accept_viva') {
            return true;
        }
        return (el.id || '').indexOf('accept_viva_delivery_') === 0;
    }

    function isVivaButton(el) {
        if (!el || el.nodeType !== 1) {
            return false;
        }
        if (el.id === 'accept_viva_button') {
            return true;
        }
        return (el.id || '').indexOf('accept_viva_delivery_button_') === 0;
    }

    function lockForm(form) {
        form.dataset.vivaSubmitted = '1';
        var btn = form.querySelector('.o_portal_sign_submit');
        if (btn) {
            btn.disabled = true;
            btn.classList.add('disabled', 'pe-none');
        }
    }

    // The stock SignatureForm renders its OWN nested <form> (no id) inside
    // the Viva form element — closest('form') from the submit button lands
    // on that anonymous inner form, so isVivaForm() never matched and the
    // page-lifetime lock silently never engaged for the SO form (user
    // report 2026-08-19: "no loading effect and it can be spam click").
    // Walk UP the DOM to the first ancestor whose id is a Viva form id.
    function findVivaForm(el) {
        while (el && el.nodeType === 1) {
            if (isVivaForm(el)) {
                return el;
            }
            el = el.parentNode;
        }
        return null;
    }

    // Capture phase: runs before the OWL component's own click handler, so
    // the flag is set before the first RPC fires and every later click on
    // the submit button is blocked.
    document.addEventListener('click', function (ev) {
        var target = ev.target;
        if (!target || typeof target.closest !== 'function') {
            return;
        }
        // A submit button inside a Viva form.
        var formEl = target.closest('.o_portal_sign_submit');
        if (formEl) {
            var form = findVivaForm(formEl);
            if (form) {
                if (form.dataset.vivaSubmitted === '1') {
                    ev.preventDefault();
                    ev.stopPropagation();
                    return;
                }
                lockForm(form);
                return;
            }
        }
        // A Viva modal opener button.
        var opener = target.closest('[data-bs-toggle="modal"]');
        if (opener && isVivaButton(opener)) {
            var targetForm = null;
            if (opener.id === 'accept_viva_button') {
                targetForm = document.getElementById('accept_viva');
            } else {
                targetForm = document.getElementById(
                    'accept_viva_delivery_' + opener.id.replace('accept_viva_delivery_button_', ''));
            }
            if (targetForm && targetForm.dataset.vivaSubmitted === '1') {
                ev.preventDefault();
                ev.stopPropagation();
            }
        }
    }, true);

    // Also block Enter-key / programmatic re-submits of locked forms.
    document.addEventListener('submit', function (ev) {
        var form = ev.target;
        if (form && isVivaForm(form) && form.dataset.vivaSubmitted === '1') {
            ev.preventDefault();
            ev.stopPropagation();
        }
    }, true);
})();
