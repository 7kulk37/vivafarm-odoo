from odoo import api, fields, models


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

    # ── Turnover monitor (VS-18) ──
    # Early-warning for the VAT registration trigger: 1.8M THB annual
    # turnover (30-day registration window). NOTE: 600k is the statutory
    # FLOOR the exemption can't go below (มาตรา 81/1), NOT the operative
    # threshold — the actual small-business exemption is 1.8M (Royal
    # Decree). A 600k alarm would false-alarm, so only 1.8M is flagged.
    viva_turnover_12m = fields.Monetary(
        string='Turnover (12 months)',
        currency_field='currency_id',
        compute='_compute_viva_turnover',
        help='Total posted sales (out_invoice + out_refund net) in the '
             'trailing 12 months — the VAT registration early-warning.',
    )
    viva_turnover_1_8m = fields.Boolean(
        string='Turnover > 1.8M',
        compute='_compute_viva_turnover',
        help='Trailing-12-month turnover exceeds the 1.8M THB VAT '
             'registration threshold — register within 30 days (มาตรา 81/1, '
             '§90/2 fine if missed).',
    )

    # ── PP.36 / self-accounting note (VS-17) ──
    # Informational only: ภ.พ.36 reverse-charge self-accounting applies to
    # direct foreign digital/software purchases (import of services), due
    # 7th of the following month. Only actionable once VAT-registered —
    # VivaFarm is §81(1)-exempt today, so this is a note, not a journal.
    viva_pp36_note = fields.Text(
        string='PP.36 Self-Accounting Note (VS-17)',
        help='Informational: ภ.พ.36 reverse-charge self-accounting applies '
             'to direct foreign digital/software purchases (import of '
             'services), due 7th of the following month. Only actionable '
             'once VAT-registered — VivaFarm is §81(1)-exempt today. '
             'Foreign digital purchases also trigger PND 54 WHT (income '
             'tax) even while VAT-exempt.',
    )

    @api.depends('viva_vat_registered')
    def _compute_viva_turnover(self):
        for company in self:
            today = fields.Date.context_today(self)
            from_date = today.replace(year=today.year - 1)
            moves = self.env['account.move'].search([
                ('company_id', '=', company.id),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', from_date),
                ('invoice_date', '<=', today),
            ])
            turnover = 0.0
            for m in moves:
                # out_refund amounts are POSITIVE in Odoo 19 — flip sign.
                if m.move_type == 'out_invoice':
                    turnover += m.amount_untaxed
                else:
                    turnover -= m.amount_untaxed
            company.viva_turnover_12m = turnover
            company.viva_turnover_1_8m = turnover > 1800000

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
