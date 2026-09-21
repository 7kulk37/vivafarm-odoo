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

from .rd_form_layout import (ATTACH3_HDR_TAXID_CELLS,
                             ATTACH3_ROW_TAXID_CELLS,
                             ATTACH53_HDR_TAXID_CELLS,
                             ATTACH53_ROW_TAXID_CELLS, ATTACH53_ROW_TOPS,
                             PRINTED_BRANCH_CELLS, PRINTED_POSTCODE_CELLS,
                             PRINTED_TAXID_CELLS, RD_FORM_LAYOUT)

PT2MM = 25.4 / 72.0
PT2PX = 96.0 / 72.0  # wkhtmltopdf on staging ignores mm on absolute pos; px works

def _strip_baht(text):
    """Official RD forms show amounts only — drop the trailing '฿'."""
    return (text or '').replace('\u00a0฿', '').replace('฿', '').strip()

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


def _digit_spans(vals, key, field, digits, n_segments):
    """One digit per printed box cell, centered on the measured cell centers.

    The printed X-XXXX-XXXXX-XX-X boxes are NOT uniform subdivisions of the
    AcroForm widget rect (groups of 1-4-5-2-1 with wider/narrower cells), so
    uniform N-slicing puts digits on the printed cell borders. The measured
    PRINTED_*_CELLS tables are the source of truth; fall back to uniform
    slicing only if the field has no measured cells.
    """
    if not digits:
        return
    f = _find(key, field)
    if field == 'Text1.0':
        cells = PRINTED_TAXID_CELLS.get(key)
    elif field == 'Text1.1':
        cells = PRINTED_BRANCH_CELLS.get(key)
    elif field == 'Text1.16':
        cells = PRINTED_POSTCODE_CELLS.get(key)
    else:
        cells = None  # uniform fallback
    if cells and len(cells) == len(digits):
        centers = cells
    else:
        centers = [f['x'] + f['w'] * ((i + 0.5) / float(n_segments))
                   for i in range(len(digits))]
    # slice width per digit: the printed box width where measured (postcode
    # box is a single small box, not a slice of the widget rect)
    if field == 'Text1.16' and cells and len(cells) > 1:
        # postcode: seg = measured slot pitch; font scales with it
        seg_w = (cells[-1] - cells[0]) / (len(cells) - 1)
        fs = 10
    else:
        seg_w = f['w'] / float(n_segments)
        fs = 10
    for i, ch in enumerate(digits):
        style = (
            'position: absolute; left: %spx; top: %spx; width: %spx; '
            'font-family: NotoSansThai, Lato, sans-serif; '
            'font-size: %spx; text-align: center;' % (
                round((centers[i] - seg_w / 2) * PT2PX, 1),
                round(f['y'] * PT2PX + 1, 1),
                round(seg_w * PT2PX, 1), fs))
        vals['boxes'].append({
            'key': '%s_%s_digit_%s' % (key, field, i),
            'left': round((centers[i] - seg_w / 2) * PT2PX, 1),
            'top': round(f['y'] * PT2PX, 1),
            'width': round(seg_w * PT2PX, 1),
            'style': style,
            'text': ch, 'align': 'center',
        })

def _box(vals, key, field, text, align='left', x=None, y=None, w=None):
    if x is not None:
        x_px, y_px = x * PT2PX, y * PT2PX
        w_px = w * PT2PX if w else None
    else:
        x_px, y_px, w_px = _pos_px(key, field)
    # right-aligned values must stop short of the box border: pad right 3px
    pad = 'padding-right: 1px; ' if align == 'right' else 'padding-left: 1px; '
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
        # branch: official form prints 5 separate boxes for the สาขา code;
        # 00000 = สำนักงานใหญ่ (HQ). Render one digit per box like the tax ID.
        common = [
            ('Text1.2', company.name, 'left'),
            ('Text1.19', str(av['n_rows']), 'left'),
            ('Text1.20', str(av['n_sheets']), 'left'),
            ('Text2.23', company.name, 'center'),
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

        # summary amounts (Text2.1-2.4): the printed box has a vertical divider
        # at x=509.2pt splitting บาท | สตางค์ — write the integer part right-
        # aligned to the divider and the decimals left-aligned after it, so the
        # decimal dot sits on the divider line.
        for field, amount in (('Text2.1', pv['total_income']),
                              ('Text2.2', pv['total_remit']),
                              ('Text2.3', pv['surcharge']),
                              ('Text2.4', pv['total'])):
            text = _strip_baht(amount)
            whole, _, satang = text.partition('.')
            f = _find(key, field)
            _box(vals, key, field, whole, 'right',
                 x=f['x'], y=f['y'], w=(509.2 - f['x']))
            _box(vals, key, field, (satang or '00'), 'left',
                 x=510.6, y=f['y'], w=(526.5 - 510.6))

        # granular address boxes — split the company address into the official
        # row fields: เลขที่(1.7) หมู่ที่(1.8) ตำบล/แขวง(1.12) อำเภอ/เขต(1.13)
        # จังหวัด(1.14). อาคาร/ชั้น/ห้อง/ตรอกซอย/แยก/ถนน left for hand-fill when
        # they don't apply. VivaFarm mapping: street2 = แขวง, city = เขต.
        street_parts = (company.street or '').split()
        house_no = street_parts[0] if street_parts else ''
        Moo = ''
        for i, part in enumerate(street_parts):
            if part.startswith('หมู่'):
                # 'หมู่ 1' may be one token or two ('หมู่' + '1')
                tail = part.replace('หมู่', '').strip()
                if tail:
                    Moo = tail
                elif i + 1 < len(street_parts):
                    Moo = street_parts[i + 1]
        addr_boxes = [('Text1.7', house_no), ('Text1.8', Moo),
                      ('Text1.12', company.street2 or ''),
                      ('Text1.13', company.city or ''),
                      ('Text1.14', company.state_id.name or '')]
        # same widget numbering on both covers (Text1.7..1.16)
        for f, t in addr_boxes:
            if t:
                _box(vals, key, f, t)

        # postcode: the printed box (144→335pt) reads as 5 digit slots — render
        # one digit per slot, evenly spread across the box instead of a compact
        # string sitting on the dotted line.
        _digit_spans(vals, key, 'Text1.16', (company.zip or '').replace(' ', ''), 5)

        # tax ID: one positioned digit per official box segment — uniform gaps
        # regardless of font metrics. The official box has 13 segments spanning
        # the Text1.0 rect; each digit centered in its 1/13 slice.
        # Same treatment for the 5-box branch code (Text1.1) → 00000.
        _digit_spans(vals, key, 'Text1.0', (company.vat or '').replace(' ', ''), 13)
        _digit_spans(vals, key, 'Text1.1', '00000', 5)

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
            # month grid: Radio Button10 x∈{45,122,199,275} y∈{272,287,300}
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


class ReportPndOfficial3Attach(models.AbstractModel):
    _name = 'report.vivafarm_report.report_pnd_official_attach'
    _description = 'Official ใบแนบ ภ.ง.ด.3 (landscape, bg + overlay)'

    # The AcroForm numbering differs between the first data row (mixed with the
    # header fields 1.0-1.3) and rows 2-5. Suffix = position within the row block
    # (row = 3 stacked income-type lines + name/address block).
    FIELD_MAP_1 = {'seq': '27', 'vat': '4', 'branch': '5', 'name': '6',
                   'addr': '8', 'day': '9', 'month': '15', 'year': '21',
                   'type': '10', 'rate': '11', 'amount': '12', 'wht': '13',
                   'cond': '14'}
    FIELD_MAP_N = {'seq': '27', 'vat': '1', 'branch': '2', 'name': '3',
                   'addr': '5', 'day': '6', 'month': '12', 'year': '18',
                   'type': '7', 'rate': '8', 'amount': '9', 'wht': '10',
                   'cond': '11'}

    @api.model
    def _attach_page(self, wizard, rows, sheet, n_sheets, av):
        company = self.env.company
        key = 'pnd3_attach'
        vals = {'boxes': []}
        vals['bg'] = '/vivafarm_report/static/src/forms/pnd3_attach_bg.png'
        # header: withholdER tax id — one digit per printed box cell
        # (13 boxes; digit y-band y14.5-25.9 → top ~16.4)
        _digit_spans_at(vals, key, 16.4, (company.vat or '').replace(' ', ''),
                        ATTACH3_HDR_TAXID_CELLS)
        _box(vals, key, 'Text1.2', str(sheet + 1), 'center')
        _box(vals, key, 'Text1.3', str(n_sheets), 'center')
        for i, r in enumerate(rows):
            m = self.FIELD_MAP_1 if i == 0 else self.FIELD_MAP_N
            g = i + 1
            def B(suffix, text, align='left'):
                if text:
                    _box(vals, key, 'Text%s.%s' % (g, suffix), text, align)

            B(m['seq'], str(sheet * 6 + i + 1), 'center')
            # tax ID: one digit per printed box cell (13 boxes, 1-4-5-2-1
            # groups; centers measured from the empty form, agent frame)
            if r['vat']:
                vat_digits = (r['vat'] or '').replace(' ', '')
                centers = list(ATTACH3_ROW_TAXID_CELLS)
                _digit_spans_at(vals, key, 112.6 + i * 55.5, vat_digits,
                                centers)
            B(m['name'], r['partner'])
            B(m['addr'], r['address'])
            if r.get('pay_date'):
                # วัน เดือน ปี ที่จ่าย: single line dd/mm/yyyy (BE year)
                B(m['day'], '%s/%s/%s' % (r['pay_date'].day,
                                          r['pay_date'].month,
                                          r['pay_date'].year + 543), 'center')
            B(m['type'], r['income_label'])
            B(m['rate'], r['rate'], 'center')
            # money columns: right-align to the printed column edges
            # (จำนวนเงิน col ends at 685.4 ref, ภาษี col at 781.8 ref)
            f_amt = _find(key, 'Text%s.%s' % (g, m['amount']))
            _box(vals, key, 'Text%s.%s' % (g, m['amount']), _num(r['amount']),
                 'right', x=f_amt['x'], y=f_amt['y'],
                 w=(685.4 - f_amt['x']))
            f_wht = _find(key, 'Text%s.%s' % (g, m['wht']))
            _box(vals, key, 'Text%s.%s' % (g, m['wht']), _num(r['wht']),
                 'right', x=f_wht['x'], y=f_wht['y'],
                 w=(781.8 - f_wht['x']))
            B(m['cond'], r['cond'], 'center')
        # totals row (Text6.24 / 6.25) — right-align to the column edges
        _box(vals, key, 'Text6.24', _strip_baht(av['total_amount']), 'right',
             x=607.0, y=443.0, w=(685.4 - 607.0))
        _box(vals, key, 'Text6.25', _strip_baht(av['total_wht']), 'right',
             x=707.6, y=443.0, w=(781.8 - 707.6))
        # footer signature block
        _box(vals, key, 'Text9.1', company.name)
        fdate = fields.Date.context_today(self)
        _box(vals, key, 'Text9.3', str(fdate.day))
        _box(vals, key, 'Text9.4', _MONTH_TH[fdate.month])
        _box(vals, key, 'Text9.5', str(fdate.year + 543))
        return vals

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['tax.report.wizard'].browse(docids)
        attach = self.env['report.vivafarm_report.report_wht_attach']
        av = attach._get_report_values(wizard.ids, {'pnd_type': 'pnd3'})
        rows = av['rows']
        n_sheets = max(1, -(-len(rows) // 6))
        pages = [
            self._attach_page(wizard, rows[s * 6:(s + 1) * 6], s, n_sheets, av)
            for s in range(n_sheets)
        ] or [{'boxes': [],
               'bg': '/vivafarm_report/static/src/forms/pnd3_attach_bg.png'}]
        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'pages': pages,
            'pnd_type': 'pnd3',
        }


def _digit_spans_at(vals, key, top_pt, digits, centers):
    """One digit per printed box cell at explicit y (pt) and centers (pt)."""
    if not digits or len(centers) < len(digits):
        return
    seg_w = (centers[-1] - centers[0]) / max(1, len(centers) - 1)
    for i, ch in enumerate(digits):
        style = (
            'position: absolute; left: %spx; top: %spx; width: %spx; '
            'font-family: NotoSansThai, Lato, sans-serif; '
            'font-size: 10px; text-align: center;' % (
                round((centers[i] - seg_w / 2) * PT2PX, 1),
                round(top_pt * PT2PX + 1, 1),
                round(seg_w * PT2PX, 1)))
        vals['boxes'].append({
            'key': '%s_taxidrow_%s' % (key, i),
            'left': round((centers[i] - seg_w / 2) * PT2PX, 1),
            'top': round(top_pt * PT2PX, 1),
            'width': round(seg_w * PT2PX, 1),
            'style': style,
            'text': ch, 'align': 'center',
        })


def _num(value):
    """Plain Thai-form amount: thousands comma + 2 decimals, no symbol."""
    try:
        return '{:,.2f}'.format(float(value))
    except (TypeError, ValueError):
        return ''


class ReportPndOfficial53Attach(models.AbstractModel):
    _name = 'report.vivafarm_report.report_pnd_official_attach53'
    _description = 'Official ใบแนบ ภ.ง.ด.53 (landscape, bg + overlay)'

    # Same suffix scheme for every group g (1-6): .4 seq, .5 TIN box strip,
    # .6 ชื่อ, .7/.8 ที่อยู่, .9 สาขาที่, .10 วัน/เดือน/ปีที่จ่าย,
    # .11 ประเภทเงินได้, .12 อัตรา, .13 จำนวนเงินที่จ่าย, .14 ภาษีที่หัก,
    # .15 เงื่อนไข. Totals row: Text6.28 / Text6.29. Footer: Text9.1-9.5.
    SEQ = '4'
    NAME = '6'
    ADDR1 = '7'
    DATE = '10'
    TYPE = '11'
    RATE = '12'
    PAYAMT = '13'
    TAX = '14'
    COND = '15'

    @api.model
    def _attach53_page(self, wizard, rows, sheet, n_sheets, av):
        company = self.env.company
        key = 'pnd53_attach'
        vals = {'boxes': []}
        vals['bg'] = '/vivafarm_report/static/src/forms/pnd53_attach_bg.png'
        # header: withholdER tax id — one digit per printed box cell
        _digit_spans_at(vals, key, 15.6, (company.vat or '').replace(' ', ''),
                        ATTACH53_HDR_TAXID_CELLS)
        _box(vals, key, 'Text1.2', str(sheet + 1), 'center')
        _box(vals, key, 'Text1.3', str(n_sheets), 'center')
        for i, r in enumerate(rows):
            g = i + 1
            top = ATTACH53_ROW_TOPS[i]

            def B(suffix, text, align='left'):
                if text:
                    _box(vals, key, 'Text%s.%s' % (g, suffix), text, align)

            B(self.SEQ, str(sheet * 6 + i + 1), 'center')
            # payee TIN: one digit per printed box cell (13 boxes)
            if r['vat']:
                _digit_spans_at(vals, key, top + 0.1,
                                (r['vat'] or '').replace(' ', ''),
                                ATTACH53_ROW_TAXID_CELLS)
            B(self.NAME, r['partner'])
            B(self.ADDR1, r['address'])
            if r.get('pay_date'):
                # วัน เดือน ปี ที่จ่าย: single line dd/mm/yyyy (BE year)
                B(self.DATE, '%s/%s/%s' % (r['pay_date'].day,
                                           r['pay_date'].month,
                                           r['pay_date'].year + 543),
                  'center')
            B(self.TYPE, r['income_label'])
            B(self.RATE, r['rate'], 'center')
            # money columns: right-align to the printed column rules
            # (จำนวนเงินที่จ่าย rule at 686.4 ref, ภาษี rule at 783.9 ref;
            # ~1.4pt inside, same convention as the PND3 attach)
            f_amt = _find(key, 'Text%s.%s' % (g, self.PAYAMT))
            _box(vals, key, 'Text%s.%s' % (g, self.PAYAMT), _num(r['amount']),
                 'right', x=f_amt['x'], y=f_amt['y'],
                 w=(685.0 - f_amt['x']))
            f_wht = _find(key, 'Text%s.%s' % (g, self.TAX))
            _box(vals, key, 'Text%s.%s' % (g, self.TAX), _num(r['wht']),
                 'right', x=f_wht['x'], y=f_wht['y'],
                 w=(782.4 - f_wht['x']))
            B(self.COND, r['cond'], 'center')
        # totals row (Text6.28 / 6.29) — right-align to the column rules
        _box(vals, key, 'Text6.28', _strip_baht(av['total_amount']), 'right',
             x=605.3, y=426.8, w=(685.0 - 605.3))
        _box(vals, key, 'Text6.29', _strip_baht(av['total_wht']), 'right',
             x=708.4, y=426.8, w=(782.4 - 708.4))
        # footer signature block
        _box(vals, key, 'Text9.1', company.name)
        fdate = fields.Date.context_today(self)
        _box(vals, key, 'Text9.3', str(fdate.day))
        _box(vals, key, 'Text9.4', _MONTH_TH[fdate.month])
        _box(vals, key, 'Text9.5', str(fdate.year + 543))
        return vals

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['tax.report.wizard'].browse(docids)
        attach = self.env['report.vivafarm_report.report_wht_attach']
        av = attach._get_report_values(wizard.ids, {'pnd_type': 'pnd53'})
        rows = av['rows']
        n_sheets = max(1, -(-len(rows) // 6))
        pages = [
            self._attach53_page(wizard, rows[s * 6:(s + 1) * 6], s, n_sheets,
                                av)
            for s in range(n_sheets)
        ] or [{'boxes': [],
               'bg': '/vivafarm_report/static/src/forms/pnd53_attach_bg.png'}]
        return {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'pages': pages,
            'pnd_type': 'pnd53',
        }
