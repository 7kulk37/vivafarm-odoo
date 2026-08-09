from odoo import _, fields, models
from odoo.exceptions import UserError


class ReissueWarning(models.TransientModel):
    """Soft warning shown before a 2nd+ re-issue in a chain.

    The first re-issue of a tax invoice is a single click. Any further
    re-issue in the same chain (i.e. the replacement itself was voided and
    is being re-issued again) asks the user to confirm — repeated re-issues
    usually mean a mistake was papered over instead of fixed, and the audit
    trail (ป.86/2542 ข้อ 25) should be a conscious decision.
    """

    _name = 'reissue.warning'
    _description = 'Re-issue Confirmation'

    move_id = fields.Many2one('account.move', string='Invoice', required=True, readonly=True)
    reissue_count = fields.Integer(string='Times Already Re-issued', readonly=True)

    def action_confirm(self):
        """User confirmed — perform the re-issue."""
        self.ensure_one()
        return self.move_id.action_reissue()
