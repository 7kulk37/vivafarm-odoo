from odoo import api, fields, models, _

class TrainingRecord(models.Model):
    """GAP training record (F-10, มกษ. 9001-2564 ข้อ 3.7.1-3.7.3).

    One record = one worker + one training session. Multiple records per
    worker form the training history (ประวัติการฝึกอบรม) required by
    ข้อ 3.8.1 item 12. The printed record carries the worker's signature
    line (ลงชื่อผู้ปฏิบัติงาน) — ข้อ 3.8.1 requires records to be signed.
    """

    _name = 'farm.training.record'
    _description = 'GAP Training Record (F-10)'
    _order = 'date desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='restrict',
        help='Worker who attended the training (ผู้ปฏิบัติงาน)',
    )
    date = fields.Date(
        string='Training Date',
        required=True,
        default=fields.Date.context_today,
    )
    topic = fields.Selection(
        [('hygiene', 'Personal Hygiene (สุขลักษณะส่วนบุคคล)'),
         ('job', 'Job Skill (ทักษะตามหน้าที่)'),
         ('gap', 'GAP (การปฏิบัติทางการเกษตรที่ดี)')],
        string='Topic',
        required=True,
        help='Training topic mapped to มกษ. 9001-2564: '
             'hygiene = ข้อ 3.7.1, job skill = ข้อ 3.7.2, GAP = ข้อ 3.7.3',
    )
    trainer = fields.Char(
        string='Trainer',
        help='Name/role of the person who delivered the training',
    )
    notes = fields.Text(
        string='Notes',
        help='Topics covered, duration, outcome (เนื้อหาที่อบรม ผลการอบรม)',
    )

    def _get_thai_date_display(self):
        """Date as dd/MMM/2569 (Buddhist Era), matching the invoice helper."""
        if not self.date:
            return ''
        from odoo.tools.misc import format_date
        th = format_date(self.env, self.date, lang_code='th_TH',
                         date_format='dd/MMM')
        return '%s/%s' % (th, self.date.year + 543)
