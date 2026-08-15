"""Sign wizard — the INTENT step.

ETDA/ETA B.E. 2544 §26 requires the signer's intent. Signing never happens
automatically on post; the user reviews the invoice, sees the live SHA-256
and the certificate being used, and explicitly confirms.

On confirm:
  1. Render the invoice PDF once (the exact bytes that will be hashed)
  2. SHA-256 hash
  3. RSA sign (via configured signing backend)
  4. Create viva.signed.document + audit events
  5. Store the signed PDF as an immutable attachment (report-level,
     not overwritable by normal re-render)
  6. Lock the invoice (subsequent edits / reset-to-draft rejected)
"""
import base64
from datetime import datetime, timezone

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..services.signing_service import SigningService, sha256_hex


class VivaSignWizard(models.TransientModel):
    _name = 'viva.sign.wizard'
    _description = 'Sign & Lock Tax Invoice'

    move_id = fields.Many2one('account.move', string='Invoice', required=True, readonly=True)
    document_number = fields.Char(string='Document', readonly=True,
                                  related='move_id.name')
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True,
                                 related='move_id.partner_id')
    amount_total = fields.Monetary(string='Total', readonly=True,
                                   related='move_id.amount_total',
                                   currency_field='company_currency_id')
    company_currency_id = fields.Many2one('res.currency', readonly=True,
                                          related='move_id.company_currency_id')
    pdf_sha256 = fields.Char(string='Document SHA-256', readonly=True)
    certificate_subject = fields.Char(string='Signing Certificate', readonly=True)
    certificate_type = fields.Char(string='Certificate Type', readonly=True)

    def _prepare_evidence(self):
        """Compute hash + cert metadata shown on the wizard (no signing yet)."""
        self.ensure_one()
        if self.move_id.state != 'posted':
            raise UserError(_('Only posted invoices can be signed.'))
        if self.move_id._is_signed():
            raise UserError(_('This invoice is already signed.'))
        service = SigningService(self.env)
        cert_info = service.backend.certificate_info()
        return service, cert_info

    def compute_evidence(self):
        """Button: show live hash + certificate before signing."""
        self.ensure_one()
        service, cert_info = self._prepare_evidence()
        pdf_bytes = self._render_invoice_pdf()
        self.write({
            'pdf_sha256': sha256_hex(pdf_bytes),
            'certificate_subject': cert_info['subject'],
            'certificate_type': 'TEST / NON-PRODUCTION' if self._is_test_cert(cert_info) else 'PRODUCTION',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @staticmethod
    def _is_test_cert(cert_info):
        return 'Test' in cert_info.get('subject', '') or 'Test' in cert_info.get('issuer', '')

    @staticmethod
    def _to_odoo_datetime(iso_str):
        """Convert ISO-8601 (e.g. 2026-08-15T03:35:49+00:00) to Odoo Datetime
        string (naive UTC '%Y-%m-%d %H:%M:%S')."""
        if not iso_str:
            return False
        try:
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            return False

    def _render_invoice_pdf(self):
        """Render the tax invoice PDF (the exact bytes that get hashed)."""
        self.ensure_one()
        pdf_bytes = self.env['ir.actions.report']._render_qweb_pdf(
            'vivafarm_report.viva_invoice', self.move_id.ids)[0]
        return pdf_bytes

    def action_sign(self):
        """Sign & lock. Returns the signed document form."""
        self.ensure_one()
        service, cert_info = self._prepare_evidence()

        # 1. Render + hash
        pdf_bytes = self._render_invoice_pdf()
        pdf_hash = sha256_hex(pdf_bytes)

        # 2. Sign
        sig_b64, cert_info, signed_at = service.sign_pdf(pdf_bytes)

        # 3. Store the signed PDF as an immutable attachment (report-level,
        #    so normal re-renders don't overwrite it)
        attachment = self.env['ir.attachment'].create({
            'name': '%s_signed.pdf' % self.move_id.name.replace('/', '_'),
            'datas': base64.b64encode(pdf_bytes),
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'type': 'binary',
        })

        # 4. Revision chain — follow the re-issue chain (ป.86/2542 ข้อ 25):
        #    reissued invoices share reissue_root_id; the new document is
        #    Rev N+1 hashing back to the previous signed revision.
        #    If this invoice is NOT part of a reissue chain, it's Rev 1.
        chain_root = self.move_id.reissue_root_id or self.move_id
        previous_signed = self.env['viva.signed.document'].search([
            ('move_id.reissue_root_id', '=', chain_root.id),
        ], order='revision desc', limit=1)
        # Also cover the chain root itself (it has no reissue_root_id)
        if not previous_signed:
            previous_signed = self.env['viva.signed.document'].search([
                ('move_id', '=', chain_root.id),
            ], order='revision desc', limit=1)
        revision = (previous_signed.revision + 1) if previous_signed else 1
        previous_hash = previous_signed.pdf_sha256 if previous_signed else False

        signed = self.env['viva.signed.document'].create({
            'document_number': self.move_id.name,
            'document_type': 'tax_invoice',
            'odoo_model': 'account.move',
            'odoo_record_id': self.move_id.id,
            'move_id': self.move_id.id,
            'revision': revision,
            'previous_document_hash': previous_hash,
            'pdf_sha256': pdf_hash,
            'signature_b64': sig_b64,
            'public_key_pem': service.backend.public_key_pem(),
            'certificate_type': 'TEST' if self._is_test_cert(cert_info) else 'PRODUCTION',
            'certificate_subject': cert_info['subject'],
            'certificate_issuer': cert_info['issuer'],
            'certificate_serial': cert_info['serial'],
            'certificate_fingerprint': cert_info['fingerprint'],
            'certificate_valid_from': self._to_odoo_datetime(cert_info['not_before']),
            'certificate_valid_to': self._to_odoo_datetime(cert_info['not_after']),
            'signer_user_id': self.env.user.id,
            'signed_at': self._to_odoo_datetime(signed_at) or fields.Datetime.now(),
            'signed_attachment_id': attachment.id,
        })
        signed._log_event('SIGNED', detail='sha256=%s' % pdf_hash[:16])

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'viva.signed.document',
            'res_id': signed.id,
            'view_mode': 'form',
            'target': 'current',
        }
