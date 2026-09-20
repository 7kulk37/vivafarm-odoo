from odoo import api, models
from odoo.exceptions import UserError
from odoo import _
from odoo.tools import format_amount
from odoo.tools.misc import format_date


class ReportWhtAttach(models.AbstractModel):
    """Data model for ใบแนบ ภ.ง.ด.3 / ภ.ง.ด.53 (per-payee WHT schedules).

    The official ภ.ง.ด.3/53 return carries the per-payee detail on a ใบแนบ
    (attachment schedule) — one row per payee per payment (R3 edge case B:
    a slice paid in a month is its own row, PND month = payment month).
    Shares the exact same posted-line pipeline as the PND covers
    (pnd3_report._get_wht_lines + payment-period filtering + VS-10 ratio)
    so totals ALWAYS tie to the cover's summary lines.

    Row fields per the official ใบแนบ form:
      ลำดับที่ | ประเภทเงินได้ + จ่ายเป็นค่าอะไร | ชื่อ-สกุล / ชื่อนิติบุคคล |
      เลขประจำตัวผู้เสียภาษี (13 หลัก) | วันที่จ่าย | จำนวนเงินที่จ่าย |
      อัตรา % | ภาษีที่หัก | เงื่อนไข (1 = หัก ณ ที่จ่าย)
    """

    _name = 'report.vivafarm_report.report_wht_attach'
    _description = 'Thai WHT ใบแนบ (Attachment Schedule) Data'

    INCOME_LABELS = {
        'rent': ('ค่าเช่า', 'Rent'),
        'advertising': ('ค่าบริการโฆษณา', 'Advertising'),
        'transport': ('ค่าขนส่ง', 'Transport'),
        'service': ('ค่าบริการ', 'Service'),
    }

    @api.model
    def _get_income_type(self, tax):
        """Income type keyed by the tax name's type letter (same rules as
        wht_certificate._get_income_type)."""
        name = tax.name or ''
        if ' R ' in name or name.endswith(' R'):
            return 'rent'
        if ' A ' in name or name.endswith(' A'):
            return 'advertising'
        if ' T ' in name or name.endswith(' T'):
            return 'transport'
        return 'service'

    @api.model
    def _get_rows(self, wizard, tag_name):
        """One row per bill-payment in the period, in payment-date order."""
        report_pnd3 = self.env['report.vivafarm_report.report_pnd3']
        lines = report_pnd3._get_wht_lines(wizard, tag_name)
        currency = self.env.company.currency_id
        rows = []
        skipped = []
        for l in lines:
            bill = l.move_id
            partner = bill.partner_id
            # S8 guards: non-resident payees file ภ.ง.ด.54, not PND3/53;
            # Thai payees must carry a Tax ID (defense-in-depth — the VS-03
            # _post guard already blocks no-vat Thai bills).
            if partner.viva_non_resident:
                continue
            if not partner.vat:
                skipped.append(partner.name)
                continue
            pay_date = report_pnd3._payment_date_in_period(bill, wizard)
            ratio = report_pnd3._payment_ratio_in_period(bill, wizard)
            income_type = self._get_income_type(l.tax_line_id)
            th, en = self.INCOME_LABELS[income_type]
            # What the payment was for: the bill's vendor reference (the
            # vendor's own invoice number) — the "จ่ายเป็นค่าอะไร" note.
            purpose = bill.ref or bill.name or ''
            addr_parts = [x for x in (partner.street, partner.street2)
                          if x]
            rows.append({
                'pay_date': pay_date,
                'pay_date_th': '%s/%s' % (
                    format_date(self.env, pay_date, lang_code='th_TH', date_format='d/MMM'),
                    pay_date.year + 543) if pay_date else '',
                'partner': partner.name or '',
                'address': ' '.join(addr for addr in (
                    ' '.join(x for x in (partner.street, partner.street2) if x),
                    partner.city or '', partner.zip or '') if addr),
                'vat': partner.vat or '',
                'income_label': th,
                'purpose': purpose,
                'amount': l.tax_base_amount * ratio,
                'amount_fmt': format_amount(self.env, l.tax_base_amount * ratio, currency),
                'rate': '%g' % (-l.tax_line_id.amount),
                'wht': -l.balance * ratio,
                'wht_fmt': format_amount(self.env, -l.balance * ratio, currency),
                'cond': '1',
            })
        rows.sort(key=lambda r: (r['pay_date'] or wizard.date_from, r['partner']))
        if skipped:
            raise UserError(_(
                'ใบแนบ: payee(s) without Tax ID cannot appear on ภ.ง.ด.3/53: %s. '
                'Set the Tax ID on the contact first (VS-03).') % ', '.join(sorted(set(skipped))))
        return rows

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['tax.report.wizard'].browse(docids)
        # pnd_type: explicit data wins; otherwise derive from the wizard's
        # register_type (standalone HTML render passes no data).
        pnd_type = (data or {}).get('pnd_type') or (
            'pnd3' if wizard.register_type == 'pnd3' else 'pnd53')
        tag_income = 'Income PND3' if pnd_type == 'pnd3' else 'Income PND53'
        tag_remit = 'PND3' if pnd_type == 'pnd3' else 'PND53'
        rows = self._get_rows(wizard, tag_remit)
        currency = self.env.company.currency_id
        # ใบแนบ counts for the cover (จำนวนราย / จำนวนแผ่น)
        n_rows = len(rows)
        n_sheets = max(1, -(-n_rows // 10))  # 10 rows per official sheet
        thai_period = '%s ถึง %s' % (
            format_date(self.env, wizard.date_from, lang_code='th_TH', date_format='d/MMMM'),
            format_date(self.env, wizard.date_to, lang_code='th_TH', date_format='d/MMMM'),
        ) if wizard.date_from.month != wizard.date_to.month else format_date(
            self.env, wizard.date_from, lang_code='th_TH', date_format='MMMM')
        thai_period = '%s พ.ศ. %s' % (thai_period, wizard.date_from.year + 543)
        company = wizard.company_id if 'company_id' in wizard._fields else self.env.company
        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'pnd_type': pnd_type,
            'thai_period': thai_period,
            'company': company,
            'date_from': wizard.date_from,
            'date_to': wizard.date_to,
            'rows': rows,
            'n_rows': n_rows,
            'n_sheets': n_sheets,
            'total_amount': format_amount(self.env, sum(r['amount'] for r in rows), currency),
            'total_wht': format_amount(self.env, sum(r['wht'] for r in rows), currency),
        }