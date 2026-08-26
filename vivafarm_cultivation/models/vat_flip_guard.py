from odoo import fields, models, api


class FarmVatFlipGuard(models.Model):
    _name = 'farm.vat.flip.guard'
    _description = 'VAT Flip Guard Report (CL-25)'
    _rec_name = 'invoice_id'

    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        readonly=True,
        help='Invoice flagged by the guard',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        related='invoice_id.partner_id',
        readonly=True,
    )
    vat_before = fields.Char(
        string='VAT Before',
        readonly=True,
        help='Partner VAT status before the flip',
    )
    vat_after = fields.Char(
        string='VAT After',
        readonly=True,
        help='Partner VAT status after the flip',
    )
    flip_date = fields.Date(
        string='Flip Date',
        readonly=True,
        help='Invoice date when the flip was detected',
    )
    reason = fields.Text(
        string='Reason',
        readonly=True,
        help='Why the guard flagged this invoice',
    )
    flip_count = fields.Integer(
        string='Flips Found',
        compute='_compute_flip_count',
        help='Number of flips found by the last scan',
    )

    @api.depends()
    def _compute_flip_count(self):
        for record in self:
            record.flip_count = len(self.search([]))

    def _scan_flips(self):
        """CL-25: scan posted invoices for VAT treatment flips.

        A flip is flagged when a posted invoice carries tax lines but the
        partner has no VAT number (or vice versa) — i.e. the VAT treatment
        is inconsistent with the partner's registration status. This is the
        guard an auditor probes: "did this customer flip between VAT and
        non-VAT treatment mid-period?"
        """
        self.env.cr.execute("""
            DELETE FROM farm_vat_flip_guard
        """)
        self.env.cr.flush()

        invoices = self.env['account.move'].search([
            ('move_type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')),
            ('state', '=', 'posted'),
        ])

        flips = []
        for inv in invoices:
            partner = inv.partner_id
            has_tax = bool(inv.amount_tax)
            partner_vat = bool(partner.vat) if partner else False

            if has_tax and not partner_vat:
                flips.append({
                    'invoice_id': inv.id,
                    'vat_before': 'No VAT number',
                    'vat_after': 'Tax charged',
                    'flip_date': inv.invoice_date or inv.date,
                    'reason': f'Invoice {inv.name} charges tax but partner {partner.name if partner else "?"} has no VAT number',
                })
            elif not has_tax and partner_vat:
                flips.append({
                    'invoice_id': inv.id,
                    'vat_before': 'VAT registered',
                    'vat_after': 'No tax charged',
                    'flip_date': inv.invoice_date or inv.date,
                    'reason': f'Invoice {inv.name} charges no tax but partner {partner.name if partner else "?"} is VAT registered',
                })

        for f in flips:
            self.create(f)
        return len(flips)
