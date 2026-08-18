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
