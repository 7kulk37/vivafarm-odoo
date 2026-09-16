from odoo import api, fields, models
from odoo.exceptions import UserError


class FarmWorker(models.Model):
    """Worker roster — the single source of worker identity.

    Every record that previously captured a worker as free text
    (cultivation packer, daily worker log, spoilage disposal) now
    points here. GAP audits want a consistent person identity across
    F-04/F-06/F-07 records; free-text names broke that (same person
    typed three ways) and let the CL-38 double-pay bug through.
    """
    _name = 'farm.worker'
    _description = 'Farm Worker (roster)'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(string='Worker Name', required=True,
                       help="Full name as shown on ID card")
    # CL-46: owner + family live on the SAME roster (GAP wants one person
    # identity), flagged instead of being a separate list. The flag drives
    # worker-log accounting: family labor is never a wage (มาตรา 40(8)).
    is_owner_family = fields.Boolean(
        string='Owner / Family',
        default=False,
        help="Tick for the owner or a family member — their logs are GAP-only "
             "records, no wage accrual, no PND 1 Kor (Thai law มาตรา 40(8))")
    # CL-47: hr.employee twin for the hr.expense wage-payment flow — created
    # automatically for hired workers, never typed by hand. Read-only link;
    # farm.worker stays the single entry point for people.
    employee_id = fields.Many2one(
        'hr.employee',
        string='Linked Employee',
        readonly=True,
        copy=False,
        help='Auto-created for hired workers so the wage-expense flow has a '
             'payer. Owner/family members get NO employee record (มาตรา 40(8): '
             'family labor is never a wage).')
    worker_id_number = fields.Char(
        string='ID Number',
        help='National ID number (GAP worker registration; required '
             'for hired workers / PND 1 Kor)')
    active = fields.Boolean(default=True)
    notes = fields.Char(string='Notes')

    _sql_constraints = [
        ('worker_id_number_unique', 'unique(worker_id_number)',
         'This ID number is already on the roster.'),
    ]

    def _sync_employee(self):
        """CL-47: one-way sync to hr.employee — hired workers get an employee
        record (hr.expense payer); owner/family members get none (family labor
        is never employment, มาตรา 40(8)). Create-once + name propagation only."""
        HrEmployee = self.env['hr.employee'].sudo()
        for rec in self:
            if rec.is_owner_family:
                # flag flipped to family: archive the stale employee stub if any
                posted = self.env['hr.expense'].sudo().search_count(
                    [('employee_id', '=', rec.employee_id.id),
                     ('state', '!=', 'draft')])
                if rec.employee_id and not posted:
                    rec.employee_id.active = False
                    rec.employee_id = False
                continue
            if not rec.employee_id:
                existing = HrEmployee.search([('name', '=', rec.name)], limit=1)
                rec.employee_id = existing or HrEmployee.create({'name': rec.name})
            elif rec.employee_id.name != rec.name:
                rec.employee_id.name = rec.name

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        recs = super().create(vals_list)
        recs._sync_employee()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if {'name', 'is_owner_family'} & set(vals):
            self._sync_employee()
        return res