"""viva.document.audit — append-only audit trail (Thai retention evidence).

Thai Revenue Code retention practice requires preserving the evidence of
what was issued, by whom, and when. This table is APPEND-ONLY: records
are created, never updated or deleted. Override unlink to enforce.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class VivaDocumentAudit(models.Model):
    _name = 'viva.document.audit'
    _description = 'Signed Document Audit Event'
    _order = 'id asc'

    document_id = fields.Many2one('viva.signed.document', string='Document',
                                  required=True, ondelete='cascade', index=True)
    event = fields.Selection([
        ('CREATED', 'Created'),
        ('SIGNED', 'Signed'),
        ('VERIFIED', 'Verified'),
        ('REVOKED', 'Revoked'),
    ], string='Event', required=True)
    detail = fields.Char(string='Detail')
    user_id = fields.Many2one('res.users', string='User', readonly=True)
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Force user + timestamp on create (evidence integrity)."""
        for vals in vals_list:
            vals.setdefault('user_id', self.env.user.id)
            vals.setdefault('timestamp', fields.Datetime.now())
        return super().create(vals_list)

    def unlink(self):
        """Append-only: audit events cannot be deleted."""
        raise UserError('Audit events are append-only and cannot be deleted.')
