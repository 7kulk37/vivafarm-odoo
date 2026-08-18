from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    signed_by = fields.Char(string='Received By')
    signed_on = fields.Datetime(string='Received On')
    signed_position = fields.Char(string='Received Position')

    in_transit = fields.Boolean(
        string='In Transit',
        copy=False,
        help='Seller shipped the goods and emailed the delivery note; the '
             'customer has not signed yet. Shows "In Transit" (yellow badge '
             'on the portal). Cleared when the customer signs (-> done) or '
             'the seller Force-Done the delivery.',
    )

    # Extend the stock.picking state machine with "In Transit" (user design
    # 2026-08-18): Ready > In Transit > Done. Full re-declaration because the
    # base field is computed+stored; we keep the stock compute and only
    # override the result when the in_transit flag is set.
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting Another Operation'),
        ('confirmed', 'Waiting'),
        ('assigned', 'Ready'),
        ('in_transit', 'In Transit'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', compute='_compute_state',
        copy=False, index=True, readonly=True, store=True, tracking=True)

    @api.depends('move_type', 'move_ids.state', 'move_ids.picking_id', 'in_transit')
    def _compute_state(self):
        """Stock state, but show 'in_transit' when the flag is set.

        The flag is set by "Ship & Send DN" (goods shipped, awaiting customer
        signature). Once the customer signs (or the seller Force-Done), the
        flag is cleared and the underlying stock state ('done') shows again.
        """
        in_transit = self.filtered(lambda p: p.in_transit)
        super(StockPicking, in_transit)._compute_state()
        in_transit.state = 'in_transit'
        super(StockPicking, self - in_transit)._compute_state()

    def _get_thai_date_display(self, field_name):
        """Date in Thai tax-invoice style: '03/ส.ค./2569' (Buddhist Era year = CE + 543).

        Same helper as account.move._get_thai_date_display — the delivery
        note (ใบส่งสินค้า) renders its dates in the same Thai format.
        """
        self.ensure_one()
        value = self[field_name]
        if not value:
            return ''
        from odoo.tools.misc import format_date
        day_month = format_date(self.env, value, lang_code='th_TH', date_format='dd/MMM')
        return '%s/%s' % (day_month, value.year + 543)

    def action_ship_and_send_dn(self):
        """"Ship & Send DN" — mark the delivery In Transit and email the DN.

        Path B (customer-signing flow, user design 2026-08-18):
          Ready -> In Transit -> (customer signs) -> Done
        This button does NOT move stock, does NOT set quantities — it only:
          1. sets the in_transit flag (portal shows yellow "In Transit" badge),
          2. sends the customer the delivery-note email (Viva DN PDF + portal
             link to sign).
        The customer's signature later runs the Validate-equivalent
        (_complete_delivery) which moves stock and flips the picking to done.
        The stock "Validate" button is untouched and remains the direct
        Path A.
        """
        self = self.filtered(lambda p: p.state in ('assigned', 'in_transit'))
        if not self:
            raise UserError(_('Only deliveries in Ready state can be shipped.'))
        for picking in self:
            if not picking.partner_id:
                raise UserError(_('The delivery %s has no customer address.'
                                  % picking.name))
        self.write({'in_transit': True})
        tpl = self.env.ref(
            'vivafarm_report.viva_email_template_ship_delivery',
            raise_if_not_found=False)
        for picking in self:
            if tpl:
                picking.with_context(force_send=True).message_post_with_source(
                    tpl,
                    email_layout_xmlid='mail.mail_notification_layout_with_responsible_signature',
                    subtype_xmlid='mail.mt_comment',
                )
            else:
                picking.message_post(
                    body=_('Delivery %s marked In Transit.') % picking.name,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
        return True

    def _complete_delivery(self):
        """Validate-equivalent used by the customer-signing path.

        Runs the same completion the stock Validate button performs: set the
        move quantities done, pick the move lines, then _action_done() — so
        the picking transitions to 'done' (stock ledger decrements). Clears
        the in_transit flag first so the compute shows 'done', not
        'in_transit'.
        """
        self.ensure_one()
        self.write({'in_transit': False})
        for move in self.move_ids:
            if move.state != 'done' and move.state != 'cancel':
                move.quantity = move.product_uom_qty
                move.picked = True
        # Only complete if there is something to complete.
        if self.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
            self._action_done()
        return True

    def action_force_done(self):
        """Force Done — fallback when the customer never signs (user choice A).

        Visible only on in_transit deliveries. Completes the delivery the
        same way the customer's signature would (stock moves + done) WITHOUT
        the digital signature — the negotiation happened outside Odoo.
        """
        self = self.filtered(lambda p: p.state == 'in_transit')
        if not self:
            raise UserError(_('Only In Transit deliveries can be force-done.'))
        for picking in self:
            picking._complete_delivery()
            picking.message_post(
                body=_('Delivery %s force-done by the seller (customer '
                       'signature skipped — negotiated outside Odoo).')
                % picking.name,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )
        return True
