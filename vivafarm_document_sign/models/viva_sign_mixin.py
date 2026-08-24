"""Shared signing helpers for vivafarm_document_sign (Odoo AbstractModel mixin).

Pure certificate helpers that were copy-pasted across account.move,
sale.order, stock.picking and the sign wizard (review dedup, 2026-08-24).
No state — safe to inherit anywhere in vivafarm_document_sign.

MUST be an AbstractModel consumed via `_inherit`, NOT a plain Python base
class — Odoo's registry setup rebases model __bases__ and a plain mixin
breaks the merge (verified on staging 2026-08-24).
"""
from odoo import models


class VivaSignMixin(models.AbstractModel):
    _name = 'viva.sign.mixin'
    _description = 'VivaFarm signing certificate helpers'

    @staticmethod
    def _is_test_cert(cert_info):
        return 'Test' in cert_info.get('subject', '') or 'Test' in cert_info.get('issuer', '')

    @staticmethod
    def _to_odoo_datetime(iso_str):
        """Convert ISO-8601 to Odoo Datetime string (naive UTC)."""
        from datetime import datetime, timezone
        if not iso_str:
            return False
        try:
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            return False
