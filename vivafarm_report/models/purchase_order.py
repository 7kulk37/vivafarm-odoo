from odoo import models


class PurchaseOrder(models.Model):
    _inherit = ['purchase.order', 'viva.report.mixin']

    def _get_tc_text(self, lang):
        """T&C note filtered by report language: Thai-only or English-only.

        The stored note is bilingual ('Thai / English' per <li> item) with a
        duplicate <strong> header. Strip the header (the template renders its
        own section label), split each item on ' / ', and return only the
        side matching the report language.
        """
        self.ensure_one()
        if not self.note:
            return ''
        import re
        from markupsafe import Markup
        from odoo.tools.misc import html_escape
        note = self.note
        # Strip the leading <p><strong>…</strong></p> header (duplicate of the
        # template's own section label).
        note = re.sub(
            r'<\s*p[^>]*>\s*<\s*strong[^>]*>.*?<\s*/\s*strong\s*>\s*<\s*/\s*p\s*>',
            '', note, flags=re.DOTALL)
        items = re.findall(r'<\s*li[^>]*>(.*?)<\s*/\s*li\s*>', note, flags=re.DOTALL)
        if not items:
            # No <li> structure — return the header-stripped note as-is.
            return Markup(note)
        out = []
        for item in items:
            text = re.sub(r'<[^>]+>', '', item).strip()
            parts = [p.strip() for p in text.split(' / ')]
            if lang == 'th_TH':
                pick = parts[0] if parts else ''
            else:
                pick = parts[1] if len(parts) > 1 else (parts[0] if parts else '')
            out.append('<li>%s</li>' % html_escape(pick))
        return Markup('<ol>%s</ol>' % ''.join(out))
