/**
 * vivafarm_report — "Accept & Sign quotation" signature form with Position.
 *
 * Extends the stock portal SignatureForm (portal.signature_form) with a
 * mandatory Position input and passes it to /accept_viva alongside name +
 * signature. The stock form/modal are untouched: this component is mounted
 * only by vivafarm_report's own Accept & Sign modal, so the standard
 * Odoo portal accept flow keeps its exact behaviour.
 *
 * Position is an UNCONTROLLED input (no t-att-value / t-on-input): the
 * value is read from the DOM on submit. Binding the value to reactive
 * state made the input appear un-typeable after a validation error
 * (re-render re-applied the stale value — user report 2026-08-18).
 * A Reset button clears the error + position + signature so the customer
 * can re-enter after a validation failure.
 */
import { onMounted } from "@odoo/owl";
import { addLoadingEffect } from "@web/core/utils/ui";
import { rpc } from "@web/core/network/rpc";
import { redirect } from "@web/core/utils/urls";
import { registry } from "@web/core/registry";
import { SignatureForm } from "@portal/signature_form/signature_form";

export class AcceptVivaSignatureForm extends SignatureForm {
    static template = "vivafarm_report.AcceptVivaSignatureForm";

    setup() {
        super.setup();
        onMounted(() => {
            const modal_el = this.rootRef.el.closest('.modal');
            if (modal_el !== null) {
                modal_el.addEventListener('shown.bs.modal', () => {
                    this.resetForm();
                });
            }
        });
    }

    get positionInput() {
        return this.rootRef.el.querySelector('.o_web_sign_position_group input');
    }

    resetForm() {
        this.state.error = false;
        this.state.success = false;
        if (this.positionInput) {
            this.positionInput.value = "";
        }
        // Clear the Full Name (reactive signature.name) + signature canvas.
        this.signature.name = "";
        if (this.signature.resetSignature) {
            this.signature.resetSignature();
        }
        // Re-enable the submit button. The stock template disables it while
        // the signature canvas is empty (t-att-disabled="signature.
        // isSignatureEmpty ? 'disabled' : ''"), so clearing the canvas on
        // Reset left the button un-clickable. The empty-canvas case is
        // guarded in onClickSubmit.
        this.signature.isSignatureEmpty = false;
    }

    onReset() {
        this.resetForm();
    }

    /**
     * Same as the stock SignatureForm.onClickSubmit, but includes the
     * mandatory position in the RPC payload AND enforces mandatory
     * Position + Full Name (user requirement 2026-08-18: the customer
     * must enter both — do not allow leaving them empty).
     */
    async onClickSubmit() {
        const name = (this.signature.name || "").trim();
        const position = this.positionInput ? this.positionInput.value.trim() : "";
        if (!name) {
            this.state.error = "Full Name is required.";
            return;
        }
        if (!position) {
            this.state.error = "Position is required.";
            return;
        }
        if (this.signature.isSignatureEmpty) {
            this.state.error = "Signature is required.";
            return;
        }
        const button = document.querySelector('.o_portal_sign_submit')
        const icon = button.removeChild(button.firstChild)
        const restoreBtnLoading = addLoadingEffect(button);

        const signature = this.signature.getSignatureImage().split(",")[1];
        const data = await rpc(this.props.callUrl, { name, position, signature });
        if (data.force_refresh) {
            restoreBtnLoading();
            button.prepend(icon)
            if (data.redirect_url) {
                redirect(data.redirect_url);
            } else {
                window.location.reload();
            }
            // do not resolve if we reload the page
            return new Promise(() => {});
        }
        this.state.error = data.error || false;
        this.state.success = !data.error && {
            message: data.message,
            redirectUrl: data.redirect_url,
            redirectMessage: data.redirect_message,
        };
    }
}

registry.category("public_components").add(
    "vivafarm_report.accept_viva_signature_form", AcceptVivaSignatureForm);
