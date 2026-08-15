"""vivafarm_delivery_ack — customer delivery acknowledgment (ใบส่งสินค้า receipt proof).

When the seller validates a delivery (stock.picking -> done), a public
confirmation link is generated and emailed to the customer. The customer
opens it, types their name (and optionally draws a signature), and clicks
"I confirm receipt".

Evidence recorded: name, signature, timestamp, IP, user agent — appended
to an immutable audit table (same append-only pattern as the sign module).

Identity model: "whoever holds the link" — same trust model as the public
/v/<token> verify page. Fine for delivery receipt; not for high-value
contracts (that would need SMS OTP, a paid step).
"""
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class VivaDeliveryAck(models.Model):
    _name = 'viva.delivery.ack'
    _description = 'Customer Delivery Acknowledgment'
    _order = 'id desc'

    # ── Delivery identity ──
    picking_id = fields.Many2one('stock.picking', string='Delivery Order',
                                 required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one('res.partner', string='Customer',
                                 related='picking_id.partner_id', store=True, index=True)
    document_number = fields.Char(string='Delivery Number', readonly=True, copy=False)

    # ── State ──
    state = fields.Selection([
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
    ], string='State', default='pending', readonly=True, copy=False)

    # ── Public link ──
    ack_token = fields.Char(string='Acknowledgment Token', readonly=True, index=True, copy=False)

    # ── Evidence (filled on confirmation) ──
    customer_name = fields.Char(string='Customer Name', readonly=True, copy=False)
    signature_b64 = fields.Text(string='Signature (base64)', readonly=True, copy=False)
    confirmed_at = fields.Datetime(string='Confirmed At', readonly=True, copy=False)
    ip_address = fields.Char(string='IP Address', readonly=True, copy=False)
    user_agent = fields.Char(string='User Agent', readonly=True, copy=False)

    _sql_constraints = [
        ('ack_token_unique', 'unique(ack_token)', 'Acknowledgment token must be unique.'),
        ('picking_unique', 'unique(picking_id)', 'A delivery can only have one acknowledgment record.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('ack_token', secrets.token_urlsafe(24))
            if not vals.get('document_number') and vals.get('picking_id'):
                picking = self.env['stock.picking'].browse(vals['picking_id'])
                vals['document_number'] = picking.name
        return super().create(vals_list)

    def action_confirm(self, customer_name='', signature_b64='', ip='', user_agent=''):
        """Record the customer's confirmation (append-only evidence)."""
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('This delivery acknowledgment is already confirmed.'))
            if not customer_name.strip():
                raise UserError(_('Customer name is required.'))
            rec.write({
                'state': 'confirmed',
                'customer_name': customer_name.strip(),
                'signature_b64': signature_b64 or False,
                'confirmed_at': fields.Datetime.now(),
                'ip_address': ip or False,
                'user_agent': user_agent or False,
            })
            rec._log_event('DELIVERY_CONFIRMED', detail='%s (%s)' % (customer_name.strip(), ip or 'no-ip'))

    def _log_event(self, event, detail=''):
        """Append to the immutable audit trail."""
        self.env['viva.delivery.audit'].create({
            'ack_id': self.id,
            'event': event,
            'detail': detail,
        })

    def _get_ack_url(self):
        """Public acknowledgment URL for the email / portal link."""
        self.ensure_one()
        base = self.env['ir.config_parameter'].get_param(
            'vivafarm_document_sign.verify_base_url',
            self.env['ir.config_parameter'].get_param('web.base.url', ''),
        )
        return '%s/ack/%s' % (base.rstrip('/'), self.ack_token)


class VivaDeliveryAudit(models.Model):
    """Append-only audit trail for delivery acknowledgments.

    Same pattern as the sign module's viva.document.audit: records are
    created, never updated or deleted. Override unlink to enforce.
    """
    _name = 'viva.delivery.audit'
    _description = 'Delivery Acknowledgment Audit Event'
    _order = 'id asc'

    ack_id = fields.Many2one('viva.delivery.ack', string='Acknowledgment',
                             required=True, ondelete='cascade', index=True)
    event = fields.Selection([
        ('CREATED', 'Created'),
        ('DELIVERY_CONFIRMED', 'Delivery Confirmed'),
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
        raise UserError('Delivery audit events are append-only and cannot be deleted.')
