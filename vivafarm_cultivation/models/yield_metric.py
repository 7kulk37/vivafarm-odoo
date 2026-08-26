from odoo import fields, models, api


class FarmYieldMetric(models.Model):
    _name = 'farm.yield.metric'
    _description = 'Yield Metric (CL-36)'
    _rec_name = 'crop_id'

    crop_id = fields.Many2one(
        'product.product',
        string='Crop',
        readonly=True,
        help='Crop the metrics cover (live product)',
    )
    batch_count = fields.Integer(
        string='Batches',
        compute='_compute_metrics',
        store=True,
        help='Done cultivations for this crop',
    )
    total_kg = fields.Float(
        string='Total kg',
        compute='_compute_metrics',
        store=True,
    )
    avg_kg_per_batch = fields.Float(
        string='Avg kg / Batch',
        compute='_compute_metrics',
        store=True,
    )
    avg_kg_per_plant = fields.Float(
        string='Avg kg / Plant',
        compute='_compute_metrics',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    @api.depends('crop_id')
    def _compute_metrics(self):
        """CL-36: yield metrics from done cultivations."""
        Cultivation = self.env['vivafarm.cultivation']
        for record in self:
            domain = [('state', '=', 'done')]
            if record.crop_id:
                domain.append(('crop_id', '=', record.crop_id.id))
            batches = Cultivation.search(domain)
            total_kg = sum(b.packed_kg for b in batches)
            plants = sum(b.transplant_amount or 0 for b in batches)
            record.batch_count = len(batches)
            record.total_kg = total_kg
            record.avg_kg_per_batch = (total_kg / len(batches)) if batches else 0.0
            record.avg_kg_per_plant = (total_kg / plants) if plants else 0.0
