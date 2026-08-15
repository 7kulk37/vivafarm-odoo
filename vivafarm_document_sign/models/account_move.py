"""account.move extensions — server-side lock for signed tax invoices.

The lock is the "hash links back to an uneditable transaction" guarantee:
once an invoice is signed, changing its financial substance is rejected at
the ORM level (UI readonly is bypassable; this is not).

Critical legal constraint (ป.86/2542 ข้อ 25): correction of a signed
invoice is NEVER an edit — it is void + reissue with a NEW number and the
SAME date. The reissue path (vivafarm_report's action_reissue, which
creates a new move with reissue_root_id) stays OPEN. Only edits to the
signed move itself are blocked.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

#: Fields that define the financial substance of a tax invoice. If any of
#: these change on a signed move, the signature evidence is void.
PROTECTED_FIELDS = {
    'partner_id', 'invoice_date', 'date', 'ref', 'narration',
    'invoice_line_ids', 'line_ids', 'amount_total', 'amount_untaxed',
    'amount_tax', 'currency_id', 'journal_id', 'payment_reference',
    'invoice_payment_term_id', 'fiscal_position_id',
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    signed_document_id = fields.One2many(
        'viva.signed.document', 'move_id', string='Signed Documents',
        readonly=True)

    def _get_signed_documents(self):
        """Signed integrity records for this move."""
        return self.env['viva.signed.document'].search([('move_id', 'in', self.ids)])

    def _is_signed(self):
        """Whether this move has a signed integrity record."""
        return bool(self._get_signed_documents())

    def write(self, vals):
        """Reject substance changes on signed invoices (server-side lock)."""
        signed = self.filtered(lambda m: m._is_signed())
        if signed:
            protected_changed = set(vals.keys()) & PROTECTED_FIELDS
            # Deleting lines is a substance change too
            if 'line_ids' in vals:
                for cmd in vals['line_ids']:
                    if cmd[0] in (2, 3, 5):  # unlink, unlink-one, clear
                        protected_changed.add('line_ids')
            if protected_changed:
                raise UserError(_(
                    'This tax invoice has been SIGNED and locked. '
                    'Financial fields cannot be changed. '
                    'To correct it, void and re-issue with a new number '
                    '(ป.86/2542 ข้อ 25).'))
        return super().write(vals)

    def button_draft(self):
        """Block reset-to-draft on signed invoices.

        Odoo allows posted→draft reset (corrections). For a signed invoice
        this would silently break the integrity evidence — the only legal
        correction path is void + reissue (ป.86/2542 ข้อ 25).
        """
        signed = self.filtered(lambda m: m._is_signed())
        if signed:
            raise UserError(_(
                'This tax invoice has been SIGNED and cannot be reset to '
                'draft. To correct it, void and re-issue with a new number '
                '(ป.86/2542 ข้อ 25).'))
        return super().button_draft()

    def _post(self, soft=True):
        """When posting, if this move replaces a signed invoice (reissue),
        nothing extra needed — the NEW move gets its own signature later.
        """
        return super()._post(soft=soft)
