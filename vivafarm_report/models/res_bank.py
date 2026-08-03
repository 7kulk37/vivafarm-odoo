from odoo import models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    def _get_additional_data_field(self, comment):
        """Embed the invoice reference in the Thai EMV QR code (tag 62,
        sub-tag 01 = Bill Number) when 'Include Reference' is enabled.

        Thai banking apps (KBank, SCB, ...) display the reference from
        sub-tag 01; sub-tag 05 (Reference Label) is ignored by them.
        """
        if self.country_code == 'TH':
            return self._serialize(1, comment)
        return super()._get_additional_data_field(comment)
