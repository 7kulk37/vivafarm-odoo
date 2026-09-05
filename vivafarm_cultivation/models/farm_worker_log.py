from odoo import api, fields, models
from odoo.exceptions import UserError
from datetime import timedelta


class FarmWorkerLog(models.Model):
    _name = 'farm.worker.log'
    _description = 'Farm Worker Log - Daily Worker Activity'
    _order = 'date desc, id'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        index=True,
    )
    worker_name = fields.Char(
        string='Worker Name',
        required=True,
        help="Worker's full name as shown on ID card",
    )
    worker_type = fields.Selection(
        [
            ('owner_family', 'Owner / Family (no wage accrual)'),
            ('hired', 'Hired Worker (wage accrued, PND 1 Kor)'),
        ],
        string='Worker Type',
        default='owner_family',
        required=True,
        help=(
            'Thai law: only GENUINE HIRED WORKER wages are deductible '
            '(มาตรา 40(8)) and only they accrue Dr 113400 WIP / Cr 222100. '
            'Owner/family labor is the return on the business — record it '
            'for GAP traceability only, never as a wage (consult 2026-09-04).'
        ),
    )
    worker_id_number = fields.Char(
        string='ID Number',
        help='National ID number (GAP worker registration; required for hired workers / PND 1 Kor)',
    )
    task_description = fields.Text(
        string='Task Description',
        required=True,
        help='What work was done (e.g. "Harvest C1+C2, pack 10kg")',
    )
    safety_briefing = fields.Boolean(
        string='Safety Briefing Given',
        default=True,
        help='GAP hygiene and safety briefing confirmed',
    )
    wage_amount = fields.Float(
        string='Wage (THB)',
        digits=(8, 0),
        default=350.0,
        help='Daily wage in Thai Baht (hired workers only; owner/family logs carry no wage)',
    )
    working_hours = fields.Float(
        string='Working Hours',
        digits=(4, 1),
        default=8.0,
        help='Hours worked (default 8)',
    )
    lot_ids = fields.Many2many(
        'stock.lot',
        string='Batches Worked',
        help='Which farm batches were worked on today',
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('canceled', 'Canceled'),
        ],
        string='Status',
        default='draft',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    ref = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        help='Auto-generated reference number',
    )
    # CL-08: GAP 3.8.1 signature pair — who did the work + who confirmed
    performed_by = fields.Char(
        string='Performed By',
        help='Worker who performed the task (GAP 3.8.1 signature)',
    )
    confirmed_by = fields.Many2one(
        'res.users',
        string='Confirmed By',
        readonly=True,
        copy=False,
        help='User who confirmed the record (bound at confirm = digital signature)',
    )
    auto_recalculation_enabled = fields.Boolean(
        string='Auto Recalc Enabled',
        compute='_compute_auto_recalculation_enabled',
    )

    @api.depends('date', 'worker_name')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.date:
                parts.append(str(record.date))
            if record.worker_name:
                parts.append(record.worker_name)
            record.display_name = ' / '.join(parts) if parts else 'New Worker Log'

    @api.depends()
    def _compute_auto_recalculation_enabled(self):
        enabled = self.env['ir.config_parameter'].sudo().get_param('vivafarm.worker_log_auto_recalc', 'False').lower() == 'true'
        for record in self:
            record.auto_recalculation_enabled = enabled

    def write(self, vals):
        """Block editing non-draft records."""
        for record in self:
            if record.state != 'draft':
                other_fields = [k for k in vals if k != 'state']
                if other_fields:
                    raise UserError(f'Cannot edit a {record.state} worker log. Only draft logs can be modified.')
        return super().write(vals)

    def action_confirm(self):
        """Confirm the worker log. Only works from draft state.

        CL-05: confirming a production HIRED-worker log CAPITALIZES the wage
        into WIP (Dr 113400 / Cr 222100) — labor is a conversion cost, not a
        period expense. It flows to FG at harvest and to COGS on sale.

        Owner/family logs (worker_type = 'owner_family') are GAP-only
        records: no wage, no accrual JE, no 222100 liability — their labor
        is the return on the business, not a deductible cost (Thai law,
        มาตรา 40(8); consult 2026-09-04).

        CL-38: a HIRED worker cannot be paid twice for the same date — the
        same worker_name + date is blocked at confirm (owner logs are exempt:
        the family can help with the same task a hired worker does).
        """
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Can only confirm draft worker logs. Log {record.display_name} is in state "{record.state}".')
            if record.worker_type == 'hired':
                if not (record.worker_id_number or '').strip():
                    raise UserError(
                        f'Hired worker {record.worker_name} needs an ID Number before confirm — '
                        'it is required for the PND 1 Kor withholding register. '
                        'If this is owner/family labor, set Worker Type to Owner/Family (no accrual).'
                    )
                if not record.wage_amount or record.wage_amount <= 0:
                    raise UserError(f'Hired worker {record.worker_name} needs a positive wage amount.')
            # Audit 2026-09-05 (odoo eng P1): Odoo Char '=' is case-sensitive
            # and does not trim, so 'WORKER X' / '  Worker X  ' bypassed the
            # exact-match check and double-paid a worker for the same day.
            # Compare on a canonical form: lower-cased, whitespace-stripped.
            _nm = (record.worker_name or '').strip().lower()
            dup = self.search([
                ('worker_name', 'in', [_nm, record.worker_name or '']),
                ('date', '=', record.date),
                ('state', '=', 'confirmed'),
                ('worker_type', '=', 'hired'),
                ('id', '!=', record.id),
            ])
            if not dup:
                # SQL canonical match: ILIKE ignores case, no trim in SQL —
                # use LOWER(BTRIM()) on both sides for full normalization.
                self.env.cr.execute("""
                    SELECT id FROM farm_worker_log
                    WHERE LOWER(BTRIM(worker_name)) = %s
                      AND date = %s AND state = 'confirmed'
                      AND worker_type = 'hired' AND id != %s
                    LIMIT 1
                """, [_nm, record.date, record.id])
                dup_ids = [row[0] for row in self.env.cr.fetchall()]
                dup = self.browse(dup_ids)
            if dup:
                raise UserError(
                    f'Duplicate wage log: {record.worker_name} already has a confirmed HIRED log for {record.date} '
                    f'({dup.display_name}). A worker cannot be paid twice for the same day.'
                )
        # Zero the wage on owner/family logs so no wage can hide in reports
        self.filtered(lambda r: r.worker_type == 'owner_family').write({'wage_amount': 0.0})
        self.write({'state': 'confirmed', 'confirmed_by': self.env.user.id})
        for record in self:
            record._post_labor_accrual()
        if self.env['ir.config_parameter'].sudo().get_param('vivafarm.worker_log_auto_recalc', 'False').lower() == 'true':
            self._recalculate_direct_labor_rate()
        return True

    def _post_labor_accrual(self):
        """Capitalize the wage into WIP: Dr 113400 / Cr 222100 (CL-05).

        Thai-law gate (2026-09-04 consult): ONLY hired-worker logs accrue.
        Owner/family logs are GAP-only records — accruing their labor would
        create a false 222100 liability and claim a non-deductible cost.
        Idempotent — a second call on the same log does nothing.
        """
        self.ensure_one()
        if self.worker_type != 'hired':
            return
        if not self.wage_amount or self.wage_amount <= 0:
            return
        wip_acc = self.env['account.account'].search([('code', '=', '113400')], limit=1)
        liab_acc = self.env['account.account'].search([('code', '=', '222100')], limit=1)
        stock_journal = self.env.company.account_stock_journal_id
        if not (wip_acc and liab_acc and stock_journal):
            return
        existing = self.env['account.move'].search(
            [('ref', '=', f'LABOR-ACCRUAL-{self.id}')], limit=1)
        if existing:
            return
        je = self.env['account.move'].create({
            'journal_id': stock_journal.id,
            'date': self.date,
            'ref': f'LABOR-ACCRUAL-{self.id}',
            'line_ids': [
                (0, 0, {'account_id': wip_acc.id, 'debit': self.wage_amount, 'credit': 0.0,
                        'name': f'Direct labor accrual - {self.display_name}'}),
                (0, 0, {'account_id': liab_acc.id, 'debit': 0.0, 'credit': self.wage_amount,
                        'name': f'Direct labor accrual - {self.display_name}'}),
            ],
        })
        je.action_post()

    def _reverse_labor_accrual(self):
        """Reverse the WIP accrual when a confirmed log is canceled (CL-05)."""
        self.ensure_one()
        je = self.env['account.move'].search(
            [('ref', '=', f'LABOR-ACCRUAL-{self.id}')], limit=1)
        if je and je.state == 'posted':
            rev = je._reverse_moves(
                default_values_list=[{'ref': f'LABOR-ACCRUAL-REV-{self.id}'}])
            for r in rev:
                r.action_post()

    def action_cancel(self):
        """Cancel the worker log. Only works from confirmed state.

        CL-05: canceling reverses the WIP accrual (the wage is no longer a
        conversion cost of any batch).
        """
        for record in self:
            if record.state != 'confirmed':
                raise UserError(f'Can only cancel confirmed worker logs. Log {record.display_name} is in state "{record.state}".')
        for record in self:
            record._reverse_labor_accrual()
        self.write({'state': 'canceled'})
        if self.env['ir.config_parameter'].sudo().get_param('vivafarm.worker_log_auto_recalc', 'False').lower() == 'true':
            self._recalculate_direct_labor_rate()
        return True

    def _get_direct_labor_product(self):
        return self.env['product.product'].search([
            ('product_tmpl_id.name', '=', 'Direct Labor Allocation'),
        ], limit=1)

    def _recalculate_direct_labor_rate(self):
        """Set Direct Labor Allocation standard_price to wage per cultivation-day.

        _compute_labor_share() now returns daily_rate * duration. So the rate
        must be total_wage / total_cultivation_days (sum of all cultivation
        durations). This ensures sum over all cultivations = total_wage.
        """
        product = self._get_direct_labor_product()
        if not product:
            raise UserError('Direct Labor Allocation product not found. Run setup to create it.')
        logs = self.search([('state', '=', 'confirmed'), ('worker_type', '=', 'hired')])
        if not logs:
            product.product_tmpl_id.standard_price = 0.0
            return 0.0
        total_wage = sum(log.wage_amount for log in logs)

        # Sum total cultivation-days across all cultivations
        cultivations = self.env['vivafarm.cultivation'].search([
            ('state', 'not in', ['draft', 'canceled']),
        ])
        total_days = 0
        for cul in cultivations:
            start = cul.plant_date
            end = cul.harvest_date
            if start and end:
                total_days += (end - start).days + 1

        if total_days <= 0:
            product.product_tmpl_id.standard_price = 0.0
            return 0.0

        rate = total_wage / total_days
        product.product_tmpl_id.standard_price = rate
        return rate

    def action_recalculate_direct_labor_rate(self):
        """Manual button: recalculate direct labor rate now."""
        rate = self._recalculate_direct_labor_rate()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Direct Labor Rate',
                'message': f'Direct Labor Allocation rate updated to {rate:.2f} THB/Day',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_toggle_auto_recalculation(self):
        """Toggle automatic recalculation on confirm/cancel."""
        param = self.env['ir.config_parameter'].sudo()
        key = 'vivafarm.worker_log_auto_recalc'
        current = param.get_param(key, 'False').lower() == 'true'
        param.set_param(key, 'False' if current else 'True')
        new_state = 'ON' if not current else 'OFF'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Auto Recalculation',
                'message': f'Auto recalculation is now {new_state}',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_enable_auto_recalculation(self):
        """Enable automatic recalculation and recalc now."""
        self.env['ir.config_parameter'].sudo().set_param('vivafarm.worker_log_auto_recalc', 'True')
        rate = self._recalculate_direct_labor_rate()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Auto Recalculation Enabled',
                'message': f'Auto recalculation is ON. Direct Labor rate is now {rate:.2f} THB/Day',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_disable_auto_recalculation(self):
        """Disable automatic recalculation."""
        self.env['ir.config_parameter'].sudo().set_param('vivafarm.worker_log_auto_recalc', 'False')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Auto Recalculation Disabled',
                'message': 'Auto recalculation is OFF. Use the manual recalculate button.',
                'type': 'warning',
                'sticky': False,
            }
        }

    @api.model
    def get_auto_recalculation_state(self):
        """Helper for UI badge/chatter."""
        return self.env['ir.config_parameter'].sudo().get_param('vivafarm.worker_log_auto_recalc', 'False').lower() == 'true'

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if not vals.get('ref'):
                vals['ref'] = self.env['ir.sequence'].next_by_code('farm.worker.log') or '/'
        return super(FarmWorkerLog, self).create(vals_list)