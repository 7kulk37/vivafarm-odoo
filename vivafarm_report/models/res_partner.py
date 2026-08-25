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
