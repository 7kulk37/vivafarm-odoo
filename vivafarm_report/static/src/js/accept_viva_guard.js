/**
 * vivafarm_report — client-side one-shot guard for "Accept & Sign quotation".
 *
 * Why (bug 2 follow-up, 2026-08-17): the stock portal.signature_form already
 * disables its submit button while the RPC is in flight (addLoadingEffect),
 * but closing and reopening the modal re-mounts the component with a fresh,
 * enabled button — so the same page can fire a second /accept_viva POST.
 * The server-side idempotency check (controllers/portal.py) turns any second
 * POST into a benign sign_ok, and this file adds the customer-side second
 * guard the user asked for: the button cannot be spammed while the server
 * is working.
 *
 * This lock is page-lifetime: after the FIRST submit attempt on this page the
 * submit button stays locked and the modal can no longer be re-opened, even
 * after the component re-mounts. A reload re-renders the page server-side —
 * if the order was already signed the button is not rendered at all.
 */
(function () {
    'use strict';

    function lockForm(form) {
        form.dataset.vivaSubmitted = '1';
        const btn = form.querySelector('.o_portal_sign_submit');
        if (btn) {
            btn.disabled = true;
            btn.classList.add('disabled', 'pe-none');
        }
    }

    // Capture phase: runs before the OWL component's own click handler, so
    // the flag is set before the first RPC fires and every later click on
    // the submit button is blocked.
    document.addEventListener('click', function (ev) {
        const target = ev.target;
        if (!target || typeof target.closest !== 'function') {
            return;
        }
        const form = document.getElementById('accept_viva');
        if (!form) {
            return;
        }
        if (target.closest('#accept_viva .o_portal_sign_submit')) {
            if (form.dataset.vivaSubmitted === '1') {
                ev.preventDefault();
                ev.stopPropagation();
                return;
            }
            lockForm(form);
            return;
        }
        // Once submitted, the sidebar opener must not re-open the modal.
        if (form.dataset.vivaSubmitted === '1'
                && target.closest('#accept_viva_button')) {
            ev.preventDefault();
            ev.stopPropagation();
        }
    }, true);

    const form = document.getElementById('accept_viva');
    if (form) {
        // Also block Enter-key / programmatic re-submits of the form.
        form.addEventListener('submit', function (ev) {
            if (form.dataset.vivaSubmitted === '1') {
                ev.preventDefault();
                ev.stopPropagation();
            }
        });
    }
})();
