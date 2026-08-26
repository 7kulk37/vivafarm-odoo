from odoo import fields, models, api
from odoo.exceptions import UserError


class FarmSpoilageDisposal(models.Model):
    _name = 'farm.spoilage.disposal'
    _description = 'Spoilage Disposal Record (CL-06/CL-22)'
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
    )
    cultivation_id = fields.Many2one(
        'vivafarm.cultivation',
        string='Cultivation',
        help='The batch the spoilage came from',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Lot',
        help='Live or packed lot being disposed',
    )
    quantity = fields.Float(
        string='Quantity',
        required=True,
        help='Units disposed (plants or kg)',
    )
    classification = fields.Selection([
        ('normal', 'Normal (≤5%)'),
        ('abnormal', 'Abnormal (>5%)'),
    ], string='Classification', default='abnormal', required=True,
       help='CL-06: normal spoilage is absorbed into FG; abnormal is a period expense.')
    # CL-22: non-sale removal type — every removal from the sale stream is
    # flagged. Feed sale is REVENUE (a sale), never a loss.
    removal_type = fields.Selection([
        ('spoilage', 'Spoilage'),
        ('flood_loss', 'Flood / Disaster Loss'),
        ('donation', 'Donation'),
        ('sample', 'Sample / Tasting'),
        ('feed_sale', 'Feed Sale (revenue)'),
        ('buyer_return', 'Buyer Return'),
    ], string='Removal Type', default='spoilage', required=True,
       help='CL-22: why produce left the sale stream. Feed sale is revenue.')
    is_revenue = fields.Boolean(
        string='Is Revenue', compute='_compute_revenue_loss', store=True,
        help='True when the removal is a sale (feed sale) that posts to revenue.')
    is_loss = fields.Boolean(
        string='Is Loss', compute='_compute_revenue_loss', store=True,
        help='True when the removal is a loss (spoilage, flood, donation, sample, return).')
    reason = fields.Text(
        string='Reason',
        help='Why the produce was rejected (disease, damage, operator error)',
    )
    destination = fields.Char(
        string='Disposed To',
        help='Where it went (waste bin, feed buyer, compost)',
    )
    worker_name = fields.Char(
        string='Disposed By',
        help='Worker who performed the disposal (GAP 3.8.1 signature)',
    )
    photo_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Photo Evidence',
        help='Optional photo proving the produce never entered the sale stream',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('canceled', 'Canceled'),
    ], string='Status', default='draft', required=True)
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
        help='Worker who performed the disposal (GAP 3.8.1 signature)',
    )
    confirmed_by = fields.Many2one(
        'res.users',
        string='Confirmed By',
        readonly=True,
        copy=False,
        help='User who confirmed the record (bound at confirm = digital signature)',
    )

    @api.depends('removal_type')
    def _compute_revenue_loss(self):
        """CL-22: feed sale is revenue; all other removals are losses."""
        for record in self:
            record.is_revenue = record.removal_type == 'feed_sale'
            record.is_loss = record.removal_type != 'feed_sale'

    @api.depends('date', 'cultivation_id')
    def _compute_display_name(self):
        for record in self:
            parts = []
            if record.date:
                parts.append(str(record.date))
            if record.cultivation_id:
                parts.append(record.cultivation_id.name)
            record.display_name = ' / '.join(parts) if parts else 'New Disposal'

    def write(self, vals):
        """Block editing non-draft records."""
        for record in self:
            if record.state != 'draft':
                other_fields = [k for k in vals if k != 'state']
                if other_fields:
                    raise UserError(f'Cannot edit a {record.state} disposal record. Only draft records can be modified.')
        return super().write(vals)

    def action_confirm(self):
        """Confirm the disposal record (GAP 3.8.1: signed by the worker).

        CL-08: confirm binds the confirming user as the digital signature.
        """
        for record in self:
            if record.state != 'draft':
                raise UserError(f'Can only confirm draft disposal records. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'confirmed', 'confirmed_by': self.env.user.id})
        return True

    def action_cancel(self):
        """Cancel the disposal record."""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(f'Can only cancel confirmed disposal records. Record {record.display_name} is in state "{record.state}".')
        self.write({'state': 'canceled'})
        return True

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if not vals.get('ref'):
                vals['ref'] = self.env['ir.sequence'].next_by_code('farm.spoilage.disposal') or '/'
        return super(FarmSpoilageDisposal, self).create(vals_list)
