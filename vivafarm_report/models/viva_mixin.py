"""Shared report helpers for VivaFarm models (Odoo AbstractModel mixin).

Pure display helpers that were copy-pasted across account.move, sale.order,
stock.picking, account.payment and purchase.order (review dedup, 2026-08-24).
No stored-bytes invariant, no state — safe to inherit anywhere in
vivafarm_report.

MUST be an AbstractModel consumed via `_inherit`, NOT a plain Python base
class: Odoo's registry setup rebases model __bases__ to merge multi-module
inherits, and a plain mixin breaks that with
`TypeError: __bases__ assignment: ... object layout differs` (verified on
staging 2026-08-24 — first mixin attempt crashed the upgrade).
"""
from odoo import models


class VivaReportMixin(models.AbstractModel):
    _name = 'viva.report.mixin'
    _description = 'VivaFarm report display helpers (Thai dates)'

    def _get_thai_date_display(self, field_name):
        """Date in Thai tax-invoice style: '03/ส.ค./2569' (Buddhist Era year = CE + 543).

        Babel has no Buddhist calendar engine, so the TH report computes the
        day/month via the Thai locale (dd/MMM -> '03/ส.ค.') and appends the
        Buddhist Era year (Gregorian year + 543).
        """
        self.ensure_one()
        value = self[field_name]
        if not value:
            return ''
        from odoo.tools.misc import format_date
        day_month = format_date(self.env, value, lang_code='th_TH', date_format='dd/MMM')
        return '%s/%s' % (day_month, value.year + 543)

    def _get_viva_datetime_display(self, field_name):
        """Datetime in the report sign-section style: '2026-08-20 23:23:51'
        (Bangkok local, Asia/Bangkok UTC+7).

        Datetime fields are stored UTC; the report must show the local
        wall-clock time the customer sees, not the UTC value.
        """
        self.ensure_one()
        value = self[field_name]
        if not value:
            return ''
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        utc = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return utc.astimezone(ZoneInfo('Asia/Bangkok')).strftime('%Y-%m-%d %H:%M:%S')
