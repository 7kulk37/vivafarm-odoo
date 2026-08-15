{
    'name': 'VivaFarm Delivery Acknowledgment',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Customer delivery confirmation (ใบส่งสินค้า receipt proof)',
    'description': """
VivaFarm Delivery Acknowledgment
================================
When the seller validates a delivery (stock.picking -> done), a public
confirmation link is generated and emailed to the customer in a separate
"Delivery Confirmation" email. The customer opens the link, types their
name (and optionally draws a signature), and clicks "I confirm receipt".

Evidence recorded: name, signature, timestamp, IP, user agent — appended
to an immutable audit table (same append-only pattern as the sign module).

The acknowledgment line prints on the Delivery Note (ใบส่งสินค้า):
"Received by: [name] — [date/time]".

NOT a blocker: the seller's validation remains the authoritative delivery
record; the ack is additional proof of receipt (GAP / audit evidence).
""",
    'depends': ['stock', 'portal', 'vivafarm_report'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template_delivery_ack.xml',
        'views/delivery_ack_views.xml',
        'views/ack_templates.xml',
        'views/report_viva_delivery_note_ack.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
