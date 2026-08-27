"""res.config.settings — Paperless archive configuration page."""
from odoo import fields, models


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
