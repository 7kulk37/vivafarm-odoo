"""Function tests for vivafarm_delivery_ack (run on test_sign DB).

Covers: ack record creation on delivery validation, token generation,
confirmation with evidence, append-only audit, double-confirm rejection,
and the delivery-note ack line rendering.
"""
import base64
import hashlib

from odoo.exceptions import UserError

PASS = 0
FAIL = 0


def check(label, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  PASS: %s %s' % (label, detail))
    else:
        FAIL += 1
        print('  FAIL: %s %s' % (label, detail))


def make_delivery():
    """Create a minimal outgoing delivery for Test Sign Customer (id 19)."""
    partner = env['res.partner'].browse(19)
    product = env['product.product'].search([('name', 'ilike', 'Fresh Lettuce')], limit=1)
    if not product:
        product = env['product.product'].create({
            'name': 'Fresh Lettuce (ผักกาดหอม)',
            'type': 'consu',
            'is_storable': True,
            'categ_id': env.ref('product.product_category_goods').id,
            'uom_id': env.ref('uom.product_uom_kgm').id,
            'list_price': 120.0,
            'sale_ok': True,
        })
    picking_type = env['stock.picking.type'].search(
        [('code', '=', 'outgoing')], limit=1)
    picking = env['stock.picking'].create({
        'partner_id': partner.id,
        'picking_type_id': picking_type.id,
        'location_id': picking_type.default_location_src_id.id,
        'location_dest_id': picking_type.default_location_dest_id.id,
        'move_ids': [(0, 0, {
            'description_picking': product.name,
            'product_id': product.id,
            'product_uom_qty': 1.0,
            'product_uom': product.uom_id.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
        })],
    })
    return picking


# ── 1. Ack record created on delivery validation ──
print('=== 1. Ack creation on validation ===')
picking = make_delivery()
check('picking created', picking.id, picking.name)
picking.move_ids.quantity = 1.0
picking.move_ids._action_done()
picking._action_done()
ack = env['viva.delivery.ack'].search([('picking_id', '=', picking.id)], limit=1)
check('ack created after validation', bool(ack))
check('ack token generated', bool(ack and ack.ack_token))
check('ack state pending', ack and ack.state == 'pending')
check('ack document number', ack and ack.document_number == picking.name)
check('ack url built', ack and '/ack/%s' % ack.ack_token in ack._get_ack_url())

# ── 2. Confirmation with evidence ──
print('=== 2. Confirmation ===')
ack.action_confirm(customer_name='Test Sign Customer', ip='203.0.113.7', user_agent='curl/8')
check('state confirmed', ack.state == 'confirmed')
check('customer name stored', ack.customer_name == 'Test Sign Customer')
check('confirmed_at set', bool(ack.confirmed_at))
check('ip stored', ack.ip_address == '203.0.113.7')
audit = env['viva.delivery.audit'].search([('ack_id', '=', ack.id)], order='id asc')
check('audit event logged', any(a.event == 'DELIVERY_CONFIRMED' for a in audit))

# ── 3. Double-confirm rejected ──
print('=== 3. Double confirm ===')
try:
    ack.action_confirm(customer_name='Again')
    check('double confirm rejected', False, 'no error raised')
except UserError:
    check('double confirm rejected', True)

# ── 4. Append-only audit ──
print('=== 4. Append-only ===')
try:
    audit.unlink()
    check('audit unlink blocked', False, 'unlink allowed')
except UserError:
    check('audit unlink blocked', True)

# ── 5. Name required ──
print('=== 5. Name required ===')
ack2 = env['viva.delivery.ack'].create({'picking_id': make_delivery().id})
try:
    ack2.action_confirm(customer_name='   ')
    check('empty name rejected', False, 'no error raised')
except UserError:
    check('empty name rejected', True)

# ── 6. Delivery note ack line renders ──
print('=== 6. Delivery note ack line ===')
html = env['ir.actions.report']._render_qweb_html(
    'vivafarm_report.viva_delivery_note', [picking.id])[0].decode()
check('ack line in delivery note', 'Confirmed by:' in html and 'Test Sign Customer' in html)
check('ack date in delivery note', 'Date:' in html)

print('RESULT: %d passed, %d failed' % (PASS, FAIL))
