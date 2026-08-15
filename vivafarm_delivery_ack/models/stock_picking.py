"""stock.picking extension — generate ack link + email on delivery validation.

When the seller validates a delivery (state -> done), we:
  1. Create the viva.delivery.ack record (token known)
  2. Send the separate "Delivery Confirmation" email with the /ack/ link

The ack is NEVER a blocker: if the email fails, the delivery is still
done. The seller's validation remains the authoritative record.
"""
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    delivery_ack_id = fields.Many2one(
        'viva.delivery.ack', string='Delivery Acknowledgment',
        compute='_compute_delivery_ack', store=False)

    def _compute_delivery_ack(self):
        acks = self.env['viva.delivery.ack'].sudo().search(
            [('picking_id', 'in', self.ids)])
        by_picking = {a.picking_id.id: a for a in acks}
        for picking in self:
            picking.delivery_ack_id = by_picking.get(picking.id, False)

    def _action_done(self):
        """After validation, create the ack record + send confirmation email."""
        res = super()._action_done()
        for picking in self.filtered(lambda p: p.picking_type_code == 'outgoing' and p.partner_id):
            self.env['viva.delivery.ack'].sudo().create({
                'picking_id': picking.id,
            })
            self._send_delivery_confirmation(picking)
        return res

    def _send_delivery_confirmation(self, picking):
        """Send the separate delivery-confirmation email with the /ack/ link."""
        ack = self.env['viva.delivery.ack'].sudo().search(
            [('picking_id', '=', picking.id)], limit=1)
        if not ack:
            return
        template = self.env.ref(
            'vivafarm_delivery_ack.email_template_delivery_ack',
            raise_if_not_found=False,
        )
        if not template:
            return
        # Render with the ack record in context so the template can build the link
        template.with_context(ack_id=ack.id).send_mail(
            ack.id, force_send=True, raise_exception=False)
