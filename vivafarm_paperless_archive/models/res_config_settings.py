"""res.config.settings — Paperless archive configuration page.

The scheduled-verify controls (enable + frequency) are NOT stored in
ir.config_parameter — they drive the SAME ir.cron record that Scheduled
Actions shows ("Paperless: Verify archived copies"). set_values() writes
the cron; get_values() reads it back, so both UIs stay in sync.
"""
from odoo import fields, models
from odoo.exceptions import UserError


class ResConfigSettingsPaperless(models.TransientModel):
    _inherit = 'res.config.settings'

    paperless_base_url = fields.Char(
        string='Paperless Base URL',
        config_parameter='vivafarm_paperless_archive.base_url',
        default='http://10.10.10.15:8000')
    paperless_api_token = fields.Char(
        string='Paperless API Token',
        config_parameter='vivafarm_paperless_archive.token')
    paperless_document_type_id = fields.Integer(
        string='Paperless Document Type ID',
        config_parameter='vivafarm_paperless_archive.document_type_id')
    paperless_tag_id = fields.Integer(
        string='Paperless Tag ID',
        config_parameter='vivafarm_paperless_archive.tag_id')

    # ── Scheduled verify (drives the ir.cron, not a config param) ──
    paperless_verify_enabled = fields.Boolean(
        string='Scheduled Verify', default=True,
        help='Enable the daily archive-integrity check. Same toggle as the '
             'Scheduled Action "Paperless: Verify archived copies".')
    paperless_verify_interval = fields.Integer(
        string='Verify Every', default=1)
    paperless_verify_interval_type = fields.Selection([
        ('minutes', 'Minutes'),
        ('hours', 'Hours'),
        ('days', 'Days'),
        ('weeks', 'Weeks'),
    ], string='Verify Unit', default='days')

    def _paperless_verify_cron(self):
        return self.env['ir.cron'].sudo().search([
            ('name', '=', 'Paperless: Verify archived copies'),
        ], limit=1)

    def set_values(self):
        super().set_values()
        cron = self._paperless_verify_cron()
        if not cron:
            return
        cron.write({
            'active': self.paperless_verify_enabled,
            'interval_number': self.paperless_verify_interval or 1,
            'interval_type': self.paperless_verify_interval_type or 'days',
        })

    def get_values(self):
        res = super().get_values()
        cron = self._paperless_verify_cron()
        if cron:
            res.update({
                'paperless_verify_enabled': cron.active,
                'paperless_verify_interval': cron.interval_number,
                'paperless_verify_interval_type': cron.interval_type,
            })
        return res

    # ── Test Connection (same pattern as the mail-server test) ──
    def button_paperless_test_connection(self):
        """Verify URL + token against the Paperless API.

        Uses the values typed in the form (not the saved config), so the
        user can test before saving. Raises UserError with a readable
        message on failure; returns a success message on success.
        """
        from odoo.addons.vivafarm_paperless_archive.services.paperless_client import (
            PaperlessClient,
        )
        base_url = self.paperless_base_url or ''
        token = self.paperless_api_token or ''
        if not base_url or not token:
            raise UserError('Enter the Paperless Base URL and API Token first.')
        client = PaperlessClient(base_url, token, timeout=10)
        try:
            resp = client._get('/api/documents/', params={'page_size': 1})
        except Exception as e:
            raise UserError('Connection failed: %s' % e)
        data = resp.json()
        count = data.get('count', 0)
        version = client.server_api_version or 'unknown'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Paperless Connection OK',
                'message': ('Connected to %s — %s documents, API v%s.'
                            % (base_url, count, version)),
                'type': 'success',
                'sticky': False,
            },
        }
