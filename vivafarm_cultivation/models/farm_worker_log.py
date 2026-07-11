from odoo import api, fields, models
from odoo.exceptions import UserError


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
    worker_id_number = fields.Char(
        string='ID Number',
        help='National ID number (for GAP worker registration)',
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
        help='Daily wage in Thai Baht',
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
        """Confirm the worker log. Only works from draft state."""
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Can only confirm draft worker logs. Log {record.display_name} is in state "{record.state}".')
        self.write({'state': 'confirmed'})
        if self.env['ir.config_parameter'].sudo().get_param('vivafarm.worker_log_auto_recalc', 'False').lower() == 'true':
            self._recalculate_direct_labor_rate()
        return True

    def action_cancel(self):
        """Cancel the worker log. Only works from confirmed state."""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(f'Can only cancel confirmed worker logs. Log {record.display_name} is in state "{record.state}".')
        self.write({'state': 'canceled'})
        if self.env['ir.config_parameter'].sudo().get_param('vivafarm.worker_log_auto_recalc', 'False').lower() == 'true':
            self._recalculate_direct_labor_rate()
        return True

    def _get_direct_labor_product(self):
        return self.env['product.product'].search([
            ('product_tmpl_id.name', '=', 'Direct Labor Allocation'),
        ], limit=1)

    def _recalculate_direct_labor_rate(self):
        """Set Direct Labor Allocation standard_price to average wage per distinct confirmed day."""
        product = self._get_direct_labor_product()
        if not product:
            raise UserError('Direct Labor Allocation product not found. Run setup to create it.')
        logs = self.search([('state', '=', 'confirmed')])
        if not logs:
            product.product_tmpl_id.standard_price = 0.0
            return 0.0
        total_wage = sum(log.wage_amount for log in logs)
        distinct_days = len(set(log.date for log in logs))
        if distinct_days <= 0:
            product.product_tmpl_id.standard_price = 0.0
            return 0.0
        rate = total_wage / distinct_days
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