from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_th_signature_image = fields.Binary(
        string='Signature Image (ลายมือชื่อผู้มีอำนาจลงนาม)',
        help='Upload an image of the authorized person\'s signature for display on Thai Tax Invoices.',
    )
    l10n_th_signatory_name = fields.Char(
        string='Signatory Name (ชื่อผู้มีอำนาจลงนาม)',
        help='Name of the authorized signatory, printed under the signature image on the Quotation/SO.',
    )
    l10n_th_signatory_position = fields.Char(
        string='Signatory Position (ตำแหน่งผู้มีอำนาจลงนาม)',
        help='Position of the authorized signatory (e.g. Managing Director), printed under the signature image on the Quotation/SO.',
    )
    l10n_th_branch_name = fields.Char(
        string='Branch Name (สาขา)',
        help='Branch name for Thai Tax Invoice. Leave empty if head office.',
    )
    l10n_th_branch_number = fields.Char(
        string='Branch Number',
        help='Branch number (e.g., 00000 for head office).',
        default='00000',
    )

    # ── Future-VAT switch (VS-14) ──
    viva_vat_registered = fields.Boolean(
        string='VAT Registered',
        help='Set when the farm registers for VAT (turnover >1.8M THB, '
             '30-day window). Flips purchase VAT from non-recoverable cost '
             'to recoverable input VAT on bills dated on/after '
             'viva_vat_registered_since (forward-only, no retroactive claims).')
    viva_vat_registered_since = fields.Date(
        string='VAT Registered Since',
        help='Effective date of VAT registration. Bills dated before this '
             'keep non-recoverable purchase VAT; bills on/after flip to '
             'recoverable input VAT (มาตรา 82/5, 86/4).')

    def _get_recoverable_purchase_vat_tax(self):
        """Return (creating if needed) the recoverable purchase VAT tax.

        The flip (VS-14) swaps the non-recoverable purchase VAT for this
        recoverable tax on bills dated on/after registration. It carries the
        statutory 6./7. tags so the ภ.พ.30 input-tax lines compute. Created
        on demand — the tax only exists once the flip is actually used.
        """
        self.ensure_one()
        tax = self.env['account.tax'].search([
            ('name', '=', 'Purchase Recoverable VAT 7%'),
            ('type_tax_use', '=', 'purchase'),
        ], limit=1)
        if tax:
            return tax
        tag6 = self.env['account.account.tag'].search(
            [('name', '=', '6. Purchase amount that is entitled to deduction of input tax from output tax in tax computation')], limit=1)
        tag7 = self.env['account.account.tag'].search(
            [('name', '=', '7. Input tax (according to invoice of purchase amount in 6.)')], limit=1)
        if not tag6 or not tag7:
            # JSONB-translated names: fall back to scanning all tags.
            all_tags = self.env['account.account.tag'].search([])
            for t in all_tags:
                n = t.name
                if n and '6. Purchase amount' in n:
                    tag6 = t
                if n and '7. Input tax' in n:
                    tag7 = t
        vat_group = self.env['account.tax.group'].search([('name', '=', 'VAT')], limit=1)
        return self.env['account.tax'].create({
            'name': 'Purchase Recoverable VAT 7%',
            'type_tax_use': 'purchase',
            'amount_type': 'percent',
            'amount': 7.0,
            'description': 'Recoverable VAT 7%',
            'price_include': True,
            'tax_group_id': vat_group.id if vat_group else False,
            'invoice_repartition_line_ids': [
                (0, 0, {
                    'factor_percent': 100,
                    'repartition_type': 'base',
                    'tag_ids': [(6, 0, [tag6.id])] if tag6 else [],
                }),
                (0, 0, {
                    'factor_percent': 100,
                    'repartition_type': 'tax',
                    'tag_ids': [(6, 0, [tag7.id])] if tag7 else [],
                }),
            ],
        })

    def _get_light_tint(self, color, pct=0.92):
        """Return a light tint of a hex color (mix toward white).

        Mirrors the SCSS `mix(white, $color, 92%)` used by Odoo's Bubble/Wave
        report layouts, so the Info-row "bubble" follows the company's
        secondary_color from Settings → Configure Document Layout.
        """
        self.ensure_one()
        if not color:
            color = '#212529'  # Odoo default when unset
        c = color.lstrip('#')
        if len(c) != 6:
            return '#f8f9fa'
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        mr = round(r + (255 - r) * pct)
        mg = round(g + (255 - g) * pct)
        mb = round(b + (255 - b) * pct)
        return '#%02x%02x%02x' % (mr, mg, mb)
