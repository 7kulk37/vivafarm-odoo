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