from odoo import models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _ensure_wht_partner(self):
        """Ensure the worker's work-contact partner is WHT-ready (VS-13a).

        Casual daily workers are §40(2) hire-of-work -> PND 3 at 3%
        (3% WH P S for natural persons). The worker master stays
        hr.employee (CID in identification_id + ID-card copy per owner
        decision D10); wages are booked as vendor bills against the
        employee's work_contact_id partner so the existing machinery
        (VS-01 auto-suggest, VS-05 cert at payment, VS-06 PND3,
        VS-08 cumulative tracker) applies unchanged.

        Returns the partner.
        """
        self.ensure_one()
        partner = self.work_contact_id
        if not partner:
            partner = self.env['res.partner'].create({
                'name': self.name,
                'company_type': 'person',
                'supplier_rank': 1,
            })
            self.work_contact_id = partner.id
        vals = {
            'company_type': 'person',
            'supplier_rank': 1,
            'viva_income_type': 'service',
        }
        if self.identification_id and not partner.vat:
            vals['vat'] = self.identification_id
        partner.write(vals)
        return partner
