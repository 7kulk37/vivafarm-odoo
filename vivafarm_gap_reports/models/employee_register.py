from odoo import api, models


class ReportEmployeeRegister(models.AbstractModel):
    """Data model for the Employee Register (บัญชีลูกจ้าง, Labor Law 114).

    Per-employee report bound to ``hr.employee``. Employee ID card and
    address live on the employee's work contact partner; start date comes
    from the active ``hr.version``; wage rate is computed from
    ``farm.worker.log`` (avg THB/hour across all logged work).
    """

    _name = 'report.vivafarm_gap_reports.report_employee_register'
    _description = 'Employee Register Report Data'

    @api.model
    def _get_report_values(self, docids, data=None):
        employees = self.env['hr.employee'].browse(docids).exists()
        rows = []
        for emp in employees:
            # Address from work contact partner (falls back to company partner)
            contact = emp.work_contact_id
            address = ''
            if contact:
                parts = [contact.street or '', contact.street2 or '',
                         contact.city or '', contact.zip or '']
                if contact.state_id:
                    parts.append(contact.state_id.name or '')
                address = ', '.join(p for p in parts if p)
            # Start date from active hr.version
            start = ''
            version = self.env['hr.version'].search(
                [('employee_id', '=', emp.id), ('active', '=', True)],
                limit=1, order='id desc')
            if version and version.date_start:
                start = version.date_start
            # Wage rate from worker logs
            logs = self.env['farm.worker.log'].search(
                [('worker_name', '=', emp.name)])
            total_wage = sum(log.wage_amount or 0.0 for log in logs)
            total_hours = sum(log.working_hours or 0.0 for log in logs)
            rate = (total_wage / total_hours) if total_hours else 0.0
            rows.append({
                'employee': emp,
                'name': emp.name,
                'identification': emp.identification_id or '',
                'address': address,
                'start': start,
                'job_title': emp.job_title or '',
                'rate': rate,
                'log_count': len(logs),
            })
        return {
            'doc_ids': employees.ids,
            'doc_model': self._name,
            'docs': employees,
            'rows': rows,
        }
