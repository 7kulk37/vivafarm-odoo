import unicodedata

from odoo import api, fields, models

# English names for all 77 Thai provinces (ISO 3166-2:TH base data).
# res.country.state.name is NOT translatable in Odoo 19, so the report maps
# Thai names to English for en_US documents. Keys are NFC-normalized at load
# so lookups match regardless of Unicode composition.
_TH_STATE_EN = {
    'กรุงเทพมหานคร': 'Bangkok',
    'กระบี่': 'Krabi',
    'กาญจนบุรี': 'Kanchanaburi',
    'กาฬสินธุ์': 'Kalasin',
    'กำแพงเพชร': 'Kamphaeng Phet',
    'ขอนแก่น': 'Khon Kaen',
    'จันทบุรี': 'Chanthaburi',
    'ฉะเชิงเทรา': 'Chachoengsao',
    'ชลบุรี': 'Chonburi',
    'ชัยนาท': 'Chai Nat',
    'ชัยภูมิ': 'Chaiyaphum',
    'ชุมพร': 'Chumphon',
    'ตรัง': 'Trang',
    'ตราด': 'Trat',
    'ตาก': 'Tak',
    'นครนายก': 'Nakhon Nayok',
    'นครปฐม': 'Nakhon Pathom',
    'นครพนม': 'Nakhon Phanom',
    'นครราชสีมา': 'Nakhon Ratchasima',
    'นครศรีธรรมราช': 'Nakhon Si Thammarat',
    'นครสวรรค์': 'Nakhon Sawan',
    'นนทบุรี': 'Nonthaburi',
    'นราธิวาส': 'Narathiwat',
    'น่าน': 'Nan',
    'บึงกาฬ': 'Bueng Kan',
    'บุรีรัมย์': 'Buri Ram',
    'ปทุมธานี': 'Pathum Thani',
    'ประจวบคีรีขันธ์': 'Prachuap Khiri Khan',
    'ปราจีนบุรี': 'Prachin Buri',
    'ปัตตานี': 'Pattani',
    'พระนครศรีอยุธยา': 'Phra Nakhon Si Ayutthaya',
    'พะเยา': 'Phayao',
    'พังงา': 'Phang Nga',
    'พัทลุง': 'Phatthalung',
    'พิจิตร': 'Phichit',
    'พิษณุโลก': 'Phitsanulok',
    'เพชรบุรี': 'Phetchaburi',
    'เพชรบูรณ์': 'Phetchabun',
    'แพร่': 'Phrae',
    'ภูเก็ต': 'Phuket',
    'มหาสารคาม': 'Maha Sarakham',
    'มุกดาหาร': 'Mukdahan',
    'แม่ฮ่องสอน': 'Mae Hong Son',
    'ยโสธร': 'Yasothon',
    'ยะลา': 'Yala',
    'ระยอง': 'Rayong',
    'ระนอง': 'Ranong',
    'ราชบุรี': 'Ratchaburi',
    'ร้อยเอ็ด': 'Roi Et',
    'ลพบุรี': 'Lopburi',
    'ลำปาง': 'Lampang',
    'ลำพูน': 'Lamphun',
    'เลย': 'Loei',
    'ศรีสะเกษ': 'Si Sa Ket',
    'สกลนคร': 'Sakon Nakhon',
    'สงขลา': 'Songkhla',
    'สตูล': 'Satun',
    'สมุทรปราการ': 'Samut Prakan',
    'สมุทรสงคราม': 'Samut Songkhram',
    'สมุทรสาคร': 'Samut Sakhon',
    'สระแก้ว': 'Sa Kaeo',
    'สระบุรี': 'Saraburi',
    'สิงห์บุรี': 'Sing Buri',
    'สุโขทัย': 'Sukhothai',
    'สุพรรณบุรี': 'Suphan Buri',
    'สุราษฎร์ธานี': 'Surat Thani',
    'สุรินทร์': 'Surin',
    'หนองคาย': 'Nong Khai',
    'หนองบัวลำภู': 'Nong Bua Lam Phu',
    'อ่างทอง': 'Ang Thong',
    'อำนาจเจริญ': 'Amnat Charoen',
    'อุดรธานี': 'Udon Thani',
    'อุตรดิตถ์': 'Uttaradit',
    'อุทัยธานี': 'Uthai Thani',
    'อุบลราชธานี': 'Ubon Ratchathani',
    'เชียงราย': 'Chiang Rai',
    'เชียงใหม่': 'Chiang Mai',
}
_TH_STATE_EN = {unicodedata.normalize('NFC', k): v for k, v in _TH_STATE_EN.items()}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ── Vendor WHT classification (VS-01) ──
    # The vendor's income type drives the default withholding tax on vendor
    # bills. Classification errors (rent 5% vs service 3% vs transport 1%)
    # are the top WHT audit finding; a per-vendor default kills the class.
    # Goods purchases NEVER carry WHT (sale of goods is not on the WHT list).
    viva_income_type = fields.Selection([
        ('goods', 'Goods (no WHT)'),
        ('rent', 'Rent (5% WH C R)'),
        ('transport', 'Transport (1% WH C T)'),
        ('service', 'Service (3% WH C S / WH P S)'),
        ('advertising', 'Advertising (2% WH C A)'),
        ('other', 'Other (manual WHT)'),
    ], string='Income Type (WHT)', default='goods',
        help='Thai withholding-tax classification for this vendor. '
             'Auto-suggests the WHT tax on vendor bill lines (VS-01). '
             'Goods = no WHT; rent 5%; transport 1%; service 3%; advertising 2%.')

    viva_default_wht_tax_id = fields.Many2one(
        'account.tax', string='Default WHT Tax', compute='_compute_viva_default_wht_tax',
        help='WHT tax auto-suggested on vendor bill lines for this vendor '
             '(computed from income type + company/person).')

    # ── Non-resident vendor flag (VS-16) ──
    # Informational only: non-resident vendors are subject to 5%/15% WHT +
    # PND 54 (not PND 3/53). The _post guardrail already skips foreign
    # vendors (no Thai TIN); this flag surfaces the PND 54 path in the UI.
    viva_non_resident = fields.Boolean(
        string='Non-resident Vendor (PND 54)',
        compute='_compute_viva_non_resident',
        help='Informational: this vendor is non-resident — WHT at 5%/15% '
             'with PND 54 (ภ.ง.ด.54), not PND 3/53 (VS-16).',
    )

    @api.depends('country_id')
    def _compute_viva_non_resident(self):
        for partner in self:
            partner.viva_non_resident = bool(
                partner.country_id and partner.country_id.code != 'TH')

    viva_vat_registered_since = fields.Date(
        string='VAT Registered Since',
        help='Date this vendor became VAT-registered. A vendor tax invoice '
             'only supports the farm\'s input-VAT credit if the vendor was '
             'registered at the time (มาตรา 82/5, 86/4). Bills dated before '
             'this keep non-recoverable purchase VAT.')

    @api.depends('viva_income_type', 'company_type')
    def _compute_viva_default_wht_tax(self):
        for partner in self:
            tax = self.env['account.tax']
            if partner.viva_income_type == 'rent':
                tax = self.env['account.tax'].search(
                    [('name', '=', '5% WH C R'), ('type_tax_use', '=', 'purchase')], limit=1)
            elif partner.viva_income_type == 'transport':
                tax = self.env['account.tax'].search(
                    [('name', '=', '1% WH C T'), ('type_tax_use', '=', 'purchase')], limit=1)
            elif partner.viva_income_type == 'service':
                name = '3% WH P S' if partner.company_type == 'person' else '3% WH C S'
                tax = self.env['account.tax'].search(
                    [('name', '=', name), ('type_tax_use', '=', 'purchase')], limit=1)
            elif partner.viva_income_type == 'advertising':
                tax = self.env['account.tax'].search(
                    [('name', '=', '2% WH C A'), ('type_tax_use', '=', 'purchase')], limit=1)
            # goods / other -> no default WHT tax
            partner.viva_default_wht_tax_id = tax.id

    def _get_state_display(self, state):
        """State name in the report language.

        ``res.country.state.name`` is NOT translatable in Odoo 19 — the base
        data stores Thai names. For en_US reports, map all 77 Thai provinces
        to their English names; fall back to the stored name for any other
        state or language.
        """
        if not state:
            return ''
        if self.env.lang == 'en_US':
            return _TH_STATE_EN.get(unicodedata.normalize('NFC', state.name), state.name)
        return state.name

    def _cumulative_paid_year(self, year):
        """Total paid to this vendor in the calendar year (VS-08).

        The 1,000 THB WHT de-minimis is per-vendor CUMULATIVE per calendar
        year, not per bill: recurring bills under 1,000 each still trigger
        withholding once the annual total exceeds 1,000. Sums the reconciled
        outbound payments to this partner in the given year.
        """
        self.ensure_one()
        payments = self.env['account.payment'].search([
            ('partner_id', '=', self.id),
            ('payment_type', '=', 'outbound'),
            ('state', 'in', ('in_process', 'paid')),
            ('date', '>=', '%s-01-01' % year),
            ('date', '<=', '%s-12-31' % year),
        ])
        return sum(p.amount for p in payments)
