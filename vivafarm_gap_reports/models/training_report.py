from odoo import api, models


class ReportTrainingRecord(models.AbstractModel):
    """Data model for the Training Record (บันทึกการฝึกอบรม, F-10).

    One record per worker per training session (clauses 3.7.1-3.7.3 of
    มกษ. 9001-2564). The printed form carries the worker's signature line
    (ลงชื่อผู้ปฏิบัติงาน) as required by ข้อ 3.8.1.
    """

    _name = 'report.vivafarm_gap_reports.report_training_record'
    _description = 'Training Record Report Data'

    @api.model
    def _get_report_values(self, docids, data=None):
        records = self.env['farm.training.record'].browse(docids).exists()
        rows = []
        for rec in records:
            emp = rec.employee_id
            contact = emp.work_contact_id
            address = ''
            if contact:
                parts = [contact.street or '', contact.street2 or '',
                         contact.city or '', contact.zip or '']
                if contact.state_id:
                    parts.append(contact.state_id.name or '')
                address = ', '.join(p for p in parts if p)
            rows.append({
                'record': rec,
                'employee': emp.name or '',
                'identification': emp.identification_id or '',
                'address': address,
                'date_th': rec._get_thai_date_display(),
                'topic': rec.topic,
                'topic_label': dict(rec._fields['topic'].selection).get(
                    rec.topic, rec.topic or ''),
                'trainer': rec.trainer or '',
                'notes': rec.notes or '',
            })
        return {
            'doc_ids': records.ids,
            'doc_model': self._name,
            'docs': records,
            'rows': rows,
        }
