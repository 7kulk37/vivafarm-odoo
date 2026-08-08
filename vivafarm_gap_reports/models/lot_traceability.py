from odoo import api, models


class ReportLotTraceability(models.AbstractModel):
    """Data model for the Product Traceability / Lot History report (GAP 5.6).

    Per-lot report bound to ``stock.lot``. Computes the full genealogy for
    a packed lot:

      seed lot (cultivation.seed_lot_id)
        -> live lot (cultivation.live_lot_id)
          -> packed lot (this lot)
            -> customer deliveries (outgoing move lines)

    Plus the lot's complete move history (date, picking, from/to, qty, state)
    and the distinct customers who received it.
    """

    _name = 'report.vivafarm_gap_reports.report_lot_traceability'
    _description = 'Lot Traceability Report Data'

    @api.model
    def _get_report_values(self, docids, data=None):
        lots = self.env['stock.lot'].browse(docids)
        lots = lots.exists()
        rows = []
        for lot in lots:
            cul = self.env['vivafarm.cultivation'].search(
                [('packed_lot_id', '=', lot.id)], limit=1)
            # Move history for this lot
            moves = self.env['stock.move.line'].search(
                [('lot_id', '=', lot.id)], order='date, id')
            move_rows = []
            for ml in moves:
                picking = ml.move_id.picking_id
                move_rows.append({
                    'date': ml.date,
                    'picking': picking.name if picking else (ml.move_id.reference or ''),
                    'from': ml.location_id.name or '',
                    'to': ml.location_dest_id.name or '',
                    'qty': ml.quantity,
                    'state': ml.state,
                    'partner': picking.partner_id.name if picking and picking.partner_id else '',
                })
            # Distinct customers from outgoing moves
            customers = set()
            for ml in moves:
                picking = ml.move_id.picking_id
                if picking and picking.picking_type_code == 'outgoing' and picking.partner_id:
                    customers.add(picking.partner_id.name)
            rows.append({
                'lot': lot,
                'name': lot.name,
                'product': lot.product_id.name or '',
                'hex': lot.x_seed_lot or '',
                'cultivation': cul.name if cul else '',
                'seed_lot': cul.seed_lot_id.name if cul and cul.seed_lot_id else '',
                'live_lot': cul.live_lot_id.name if cul and cul.live_lot_id else '',
                'crop': cul.crop_id.name if cul and cul.crop_id else '',
                'bench': (cul.bench_id.name or '') if cul else '',
                'plant_date': cul.plant_date if cul else '',
                'harvest_date': cul.harvest_date if cul else '',
                'packed_kg': cul.packed_kg if cul else 0.0,
                'move_rows': move_rows,
                'customers': sorted(customers),
                'customers_str': ', '.join(sorted(customers)),
            })
        return {
            'doc_ids': lots.ids,
            'doc_model': self._name,
            'docs': lots,
            'rows': rows,
        }
