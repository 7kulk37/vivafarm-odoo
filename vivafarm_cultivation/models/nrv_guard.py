from odoo import fields, models, api


class FarmNrvGuard(models.Model):
    _name = 'farm.nrv.guard'
    _description = 'NRV Guard (CL-31)'
    _rec_name = 'product_id'

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        help='Finished-goods product evaluated',
    )
    cost = fields.Monetary(
        string='Cost (per unit)',
        currency_field='currency_id',
        compute='_evaluate',
        help='standard_price of the product (the batch cost)',
    )
    nrv = fields.Monetary(
        string='NRV (per unit)',
        currency_field='currency_id',
        compute='_evaluate',
        help='Net realizable value = expected sale price minus costs to sell',
    )
    write_down_needed = fields.Boolean(
        string='Write-Down Needed',
        compute='_evaluate',
        help='True when cost exceeds NRV — the batch should be written down',
    )
    write_down_amount = fields.Monetary(
        string='Write-Down Amount',
        currency_field='currency_id',
        compute='_evaluate',
        help='cost minus NRV when a write-down is needed',
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

    @api.depends('product_id')
    def _evaluate(self):
        """CL-31: NRV = sale price - estimated costs to sell (5% default).

        cost = standard_price (batch cost per kg)
        nrv  = list_price * 0.95 (conservative: 5% selling costs)
        """
        for record in self:
            product = record.product_id
            cost = product.standard_price
            nrv = product.list_price * 0.95
            record.cost = cost
            record.nrv = nrv
            record.write_down_needed = cost > nrv
            record.write_down_amount = max(cost - nrv, 0.0)
