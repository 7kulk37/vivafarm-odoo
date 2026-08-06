from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_state_display(self, state):
        """State name in the report language.

        ``res.country.state.name`` is NOT translatable in Odoo 19 — the base
        data stores Thai names (e.g. ``กรุงเทพมหานคร``). For en_US reports,
        map the states we use to their English names; fall back to the stored
        name for any other state or language.
        """
        if not state:
            return ''
        if self.env.lang == 'en_US':
            return {
                'กรุงเทพมหานคร': 'Bangkok',
                'สมุทรปราการ': 'Samut Prakan',
                'ภูเก็ต': 'Phuket',
            }.get(state.name, state.name)
        return state.name
