"""paperless.search.wizard — full-text search passthrough into Paperless.

The wizard queries Paperless's own search (its real strength) and shows
hits with deep links. Results are transient (stored on the wizard for
display only); nothing is written back to Paperless.
"""
from odoo import fields, models


class PaperlessSearchWizard(models.TransientModel):
    _name = 'paperless.search.wizard'
    _description = 'Paperless Full-Text Search'

    query = fields.Char(string='Search Paperless', required=True)
    result_count = fields.Integer(string='Results', readonly=True)
    result_ids = fields.One2many(
        'paperless.search.result', 'wizard_id', string='Results',
        readonly=True)

    def action_search(self):
        self.ensure_one()
        self.result_ids.unlink()
        from odoo.addons.vivafarm_paperless_archive.services.paperless_client import (
            PaperlessClient,
        )
        ICP = self.env['ir.config_parameter'].sudo()
        base_url = ICP.get_param('vivafarm_paperless_archive.base_url',
                                 'http://10.10.10.15:8000')
        token = ICP.get_param('vivafarm_paperless_archive.token', '')
        client = PaperlessClient(base_url, token, timeout=15)
        hits = client.search_documents(self.query, limit=50)
        for h in hits:
            self.env['paperless.search.result'].create({
                'wizard_id': self.id,
                'paperless_document_id': h['id'],
                'title': h['title'] or '',
                'doc_type': h['doc_type'] or '',
                'created': h['created'] or '',
                'content': h['content'] or '',
                'url': '%s/documents/%s/' % (base_url.rstrip('/'), h['id']),
            })
        self.result_count = len(hits)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class PaperlessSearchResult(models.TransientModel):
    _name = 'paperless.search.result'
    _description = 'Paperless Search Result'

    wizard_id = fields.Many2one('paperless.search.wizard', ondelete='cascade')
    paperless_document_id = fields.Integer(string='Paperless ID')
    title = fields.Char(string='Title')
    doc_type = fields.Char(string='Type')
    created = fields.Char(string='Created')
    content = fields.Text(string='Content')
    url = fields.Char(string='URL')
