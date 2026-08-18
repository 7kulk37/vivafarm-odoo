/**
 * vivafarm_report — "Accept & Sign quotation" signature form with Position.
 *
 * Extends the stock portal SignatureForm (portal.signature_form) with an
 * optional Position input and passes it to /accept_viva alongside name +
 * signature. The stock form/modal are untouched: this component is mounted
 * only by vivafarm_report's own Accept & Sign modal, so the standard
 * Odoo portal accept flow keeps its exact behaviour.
 *
 * Same method as default: the RPC payload only grows by one field
 * ({name, signature} -> {name, position, signature}) and the server
 * ignores the extra key on the standard /accept route.
 */
import { addLoadingEffect } from "@web/core/utils/ui";
import { rpc } from "@web/core/network/rpc";
import { redirect } from "@web/core/utils/urls";
import { registry } from "@web/core/registry";
import { SignatureForm } from "@portal/signature_form/signature_form";

export class AcceptVivaSignatureForm extends SignatureForm {
    static template = "vivafarm_report.AcceptVivaSignatureForm";

    setup() {
        super.setup();
        this.position = this.props.position || "";
    }

    onPositionInput(ev) {
        this.position = ev.target.value;
    }

    /**
     * Same as the stock SignatureForm.onClickSubmit, but includes the
     * optional position in the RPC payload AND enforces mandatory
     * Position + Full Name (user requirement 2026-08-18: the customer
     * must enter both — do not allow leaving them empty).
     */
    async onClickSubmit() {
        const name = (this.signature.name || "").trim();
        const position = (this.position || "").trim();
        if (!name) {
            this.state.error = "Full Name is required.";
            return;
        }
        if (!position) {
            this.state.error = "Position is required.";
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
