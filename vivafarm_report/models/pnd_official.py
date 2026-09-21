"""Data model for the OFFICIAL-FORM PND pack (S14).

Background = the official RD form rasterized from rd.go.th AcroForm PDFs
(พิมพ์ มี.ค. 2560), stored in static/src/forms/. Our data is absolutely
positioned over it using the official PDF's own AcroForm field rects
(models/rd_form_layout.py) — pt converted to mm (x25.4/72), so the overlay
lands exactly in the boxes the RD designed.

Scope V1 (fields auto-filled):
  cover: tax ID, branch, payer name, full address (single line in the first
  ที่อยู่ box), year พ.ศ., ยื่นปกติ mark, month mark, มาตรา mark, ใบแนบ
  counts (ราย/แผ่น), summary lines 1-4, signature name + filing date.
  Hand-fill after printing: granular address boxes, ยื่นเพิ่มเติมครั้งที่,
  เลขที่หนังสือ, สรรพากรพื้นที่, seal.
"""

import datetime

from odoo import api, fields, models
from odoo.tools import format_amount

from .rd_form_layout import RD_FORM_LAYOUT

PT2MM = 25.4 / 72.0
PT2PX = 96.0 / 72.0  # wkhtmltopdf on staging ignores mm on absolute pos; px works

_MONTH_TH = {
    1: 'มกราคม', 2: 'กุมภาพันธ์', 3: 'มีนาคม', 4: 'เมษายน',
    5: 'พฤษภาคม', 6: 'มิถุนายน', 7: 'กรกฎาคม', 8: 'สิงหาคม',
    9: 'กันยายน', 10: 'ตุลาคม', 11: 'พฤศจิกายน', 12: 'ธันวาคม',
}


def _pos_px(layout_key, field_name):
    """Return (left_px, top_px, width_px) of an official form field (96dpi)."""
    for f in RD_FORM_LAYOUT[layout_key]['fields']:
        if f['name'] == field_name:
            return (round(f['x'] * PT2PX, 1), round(f['y'] * PT2PX, 1),
                    round(f['w'] * PT2PX, 1))
    raise KeyError('%s / %s' % (layout_key, field_name))


def _find(layout_key, field_name, x=None, y=None, tol=6):
    """Find a field by name + optional rect position (points)."""
    for f in RD_FORM_LAYOUT[layout_key]['fields']:
        if f['name'] != field_name:
            continue
        if x is not None and abs(f['x'] - x) > tol:
            continue
        if y is not None and abs(f['y'] - y) > tol:
            continue
        return f
    raise KeyError('%s / %s (x=%s y=%s)' % (layout_key, field_name, x, y))


def _box(vals, key, field, text, align='left', x=None, y=None, w=None):
    if x is not None:
        x_px, y_px = x * PT2PX, y * PT2PX
        w_px = w * PT2PX if w else None
    else:
        x_px, y_px, w_px = _pos_px(key, field)
    # right-aligned values must stop short of the box border: pad right 3px
    pad = 'padding-right: 3px; ' if align == 'right' else 'padding-left: 1px; '
    # long digit strings need a smaller font to fit the printed box
    fs = 10 if field == 'Text1.0' else 11
    style = 'position: absolute; left: %spx; top: %spx; %s%sfont-family: NotoSansThai, Lato, sans-serif; font-size: %spx; line-height: 1.1; text-align: %s; white-space: nowrap;' % (
        round(x_px + 2, 1), round(y_px + 1, 1),
        ('width: %spx; ' % round(w_px, 1)) if w_px else '', pad, fs, align)
    vals['boxes'].append({
        'key': '%s_%s_%s' % (key, field, x or 0),
        'left': round(x_px, 1), 'top': round(y_px, 1),
        'width': round(w_px, 1) if w_px else None,
        'style': style,
        'text': text, 'align': align,
    })


def _mark(vals, key, field, x=None, y=None):
    """Checkbox tick: centered ☒ over the radio rect (found by rect pos)."""
    f = _find(key, field, x, y)
    _w, _h = f['w'] * PT2PX, f['h'] * PT2PX
    style = 'position: absolute; left: %spx; top: %spx; width: %spx; height: %spx; font-family: NotoSansThai, Lato, sans-serif; font-size: 14px; font-weight: bold; text-align: center;' % (
        round(f['x'] * PT2PX, 1), round(f['y'] * PT2PX, 1), round(_w, 1), round(_h, 1))
    vals['boxes'].append({
        'key': '%s_%s_%s_tick' % (key, field, f['x']),
        'left': round(f['x'] * PT2MM, 1),
        'top': round(f['y'] * PT2MM, 1),
        'width': round(_w, 1),
        'height': round(_h, 1),
        'style': style,
        'text': '\u2612', 'align': 'center', 'tick': True,
    })


class ReportPndOfficial(models.AbstractModel):
    _name = 'report.vivafarm_report.report_pnd_official'
    _description = 'Official RD Form PND Pack (background + overlay)'

    @api.model
    def _cover_overlay(self, wizard, pnd_type):
        vals = {'boxes': []}
        company = self.env.company
        pnd_model = self.env[
            'report.vivafarm_report.report_pnd3' if pnd_type == 'pnd3'
            else 'report.vivafarm_report.report_pnd53']
        pv = pnd_model._get_report_values(wizard.ids)
        attach = self.env['report.vivafarm_report.report_wht_attach']
        av = attach._get_report_values(wizard.ids, {'pnd_type': pnd_type})

        key = 'pnd%s_cover' % ('3' if pnd_type == 'pnd3' else '53')
        vals['bg'] = '/vivafarm_report/static/src/forms/%s' % (
            'pnd3_cover_bg.png' if pnd_type == 'pnd3' else 'pnd53_cover_bg.png')
        vals['pnd_form_name'] = 'ภ.ง.ด.3' if pnd_type == 'pnd3' else 'ภ.ง.ด.53'

        year_be = wizard.date_from.year + 543
        addr = ' '.join(filter(None, (
            company.street, company.street2, company.city, company.zip)))
        fdate = fields.Date.context_today(self)

        # --- cover text fields ---
        common = [
            ('Text1.0', company.vat or '', 'left'),
            ('Text1.1', 'สำนักงานใหญ่', 'left'),
            ('Text1.2', company.name, 'left'),
            ('Text1.3', addr, 'left'),
            ('Text1.19', str(av['n_rows']), 'left'),
            ('Text1.20', str(av['n_sheets']), 'left'),
            ('Text2.1', pv['total_income'], 'right'),
            ('Text2.2', pv['total_remit'], 'right'),
            ('Text2.3', pv['surcharge'], 'right'),
            ('Text2.4', pv['total'], 'right'),
            ('Text2.23', company.name, 'left'),
        ]
        if pnd_type == 'pnd3':
            fields_map = common + [
                ('Text1.18', str(year_be), 'left'),
            ]
        else:
            fields_map = common + [
                ('Text1.17', str(year_be), 'left'),
                ('Text1.21', str(av['n_rows']), 'left'),
                ('Text1.22', str(av['n_sheets']), 'left'),
            ]
        for field, text, align in fields_map:
            _box(vals, key, field, text, align)

        # ยื่นวันที่ / เดือน / พ.ศ.
        _box(vals, key, 'Text2.25', str(fdate.day))
        _box(vals, key, 'Text2.26', _MONTH_TH[fdate.month])
        _box(vals, key, 'Text2.27', str(fdate.year + 543))

        # --- checkbox marks ---
        if pnd_type == 'pnd3':
            # ยื่นปกติ = RB0 at (81,266); the other RB0 (177,267) = เพิ่มเติม
            _mark(vals, key, 'Radio Button0', x=81, y=266)
            # มาตรา 50 (3)(4)(5) = RB2 at (359,309)
            _mark(vals, key, 'Radio Button2', x=359, y=309)
            # month grid (column-major): x=338 holds months 1-3, 395 → 4-6,
            # 453 → 7-9, 508 → 10-12; rows top→bottom within each column
            m = wizard.date_from.month - 1
            col_x = (338, 395, 453, 508)[m // 3]
            row_y = (142, 166, 190)[m % 3]
            _mark(vals, key, 'Radio Button10', x=col_x, y=row_y)
        else:
            # PND53: ยื่นปกติ/เพิ่มเติม = RB2(369,206) / RB2(465,206)
            _mark(vals, key, 'Radio Button2', x=369, y=206)
            # มาตรา 69 ทวิ = RB0 at (380,164); (ม.3เตรส=125, ม.65จัตวา=144)
            _mark(vals, key, 'Radio Button0', x=380, y=164)
            # month grid (column-major): x=45 → months 1-4, 122 → 5-8? verify:
            # PND53 rows: y=272 row has (1)ม.ค.(45),(4)เม.ย.(122),(7)ก.ค.(199),(10)ต.ค.(275)
            # so col-major with 4 rows per column: col=(m)//4, row=(m)%4
            m = wizard.date_from.month - 1
            col_x = (45, 122, 199, 275)[m // 3]
            row_y = (272, 287, 300)[m % 3]
            _mark(vals, key, 'Radio Button10', x=col_x, y=row_y)
        return vals

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['tax.report.wizard'].browse(docids)
        pnd_type = (data or {}).get('pnd_type') or (
            'pnd3' if wizard.register_type == 'pnd3' else 'pnd53')
        vals = self._cover_overlay(wizard, pnd_type)
        vals.update({
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'pnd_type': pnd_type,
        })
        return vals


class ReportPndOfficial53(models.AbstractModel):
    _name = 'report.vivafarm_report.report_pnd_official53'
    _description = 'Official RD Form PND53 Pack'
    _inherit = 'report.vivafarm_report.report_pnd_official'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        data['pnd_type'] = 'pnd53'
        return super()._get_report_values(docids, data)