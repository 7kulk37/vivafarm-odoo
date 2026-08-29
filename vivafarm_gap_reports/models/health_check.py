from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HealthCheck(models.Model):
    """GAP worker health check (มกษ. 9001-2564 ข้อ 3.7.7).

    ข้อ 3.7.7: ผู้ปฏิบัติงานเกี่ยวกับวัตถุอันตรายทางการเกษตรได้รับการตรวจสุขภาพ
    อย่างน้อยปีละ 1 ครั้ง — workers who handle agricultural hazardous
    substances (pesticides, concentrated acid, etc.) must have a health
    check at least once a year.

    ข้อ 3.8.1 item 12 requires recording "ประวัติการฝึกอบรมและผลการตรวจสุขภาพ"
    (training history AND health check results) — this model is the health
    half of that record pair (the training half is farm.training.record).
    """

    _name = 'farm.health.check'
    _description = 'GAP Worker Health Check (ข้อ 3.7.7)'
    _order = 'date desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='restrict',
        help='Worker who received the health check (ผู้ปฏิบัติงาน)',
    )
    date = fields.Date(
        string='Check Date',
        required=True,
        default=fields.Date.context_today,
    )
    result = fields.Selection(
        [('pass', 'Pass (ผ่าน)'),
         ('fail', 'Fail (ไม่ผ่าน)'),
         ('follow_up', 'Follow-up required (ต้องติดตาม)')],
        string='Result',
        required=True,
        default='pass',
    )
    clinic = fields.Char(
        string='Clinic / Hospital',
        help='Name of the clinic or hospital that performed the check',
    )
    notes = fields.Text(
        string='Notes',
        help='Findings, restrictions, follow-up (ผลการตรวจ ข้อจำกัด การติดตาม)',
    )
    # GAP 3.8.1 signature pair — who did the work + who confirmed
    performed_by = fields.Char(
        string='Performed By',
        help='Worker who received the check (GAP 3.8.1 signature)',
    )
    confirmed_by = fields.Many2one(
        'res.users',
        string='Confirmed By',
        readonly=True,
        copy=False,
        help='User who confirmed the record (bound at confirm = digital signature)',
    )
    state = fields.Selection(
        [('draft', 'Draft'),
         ('confirmed', 'Confirmed'),
         ('canceled', 'Canceled')],
        string='Status',
        default='draft',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    'Can only confirm draft health checks. Record %s is in '
                    'state "%s".' % (rec.employee_id.name, rec.state))
        self.write({'state': 'confirmed', 'confirmed_by': self.env.user.id})
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(
                    'Can only cancel confirmed health checks. Record %s is in '
                    'state "%s".' % (rec.employee_id.name, rec.state))
        self.write({'state': 'canceled'})
        return True

    def _get_thai_date_display(self):
        """Date as dd/MMM/2569 (Buddhist Era), matching the training record."""
        if not self.date:
            return ''
        from odoo.tools.misc import format_date
        th = format_date(self.env, self.date, lang_code='th_TH',
                         date_format='dd/MMM')
        return '%s/%s' % (th, self.date.year + 543)
