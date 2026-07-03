{
    'name': 'Hydroponic Cultivation',
    'version': '1.1.0',
    'category': 'Manufacturing/Agriculture',
    'summary': 'Cultivation cycle management - seed to harvest in one record',
    'description': """
        Simple cultivation operations for hydroponic leafy green production.

        - Create a Cultivation record (like a PO) with status tracking
        - Click Plant: consumes seeds, creates live plants
        - Click Transplant: moves live plants to bench
        - Click Harvest: consumes live plants, creates packed goods
        - Status: Draft → Planted → Growing → Harvested → Done

        Uses stock moves with Production location as pass-through buffer.
        No BOMs, no work orders, no cost calculations.
    """,
    'depends': ['stock', 'vivafarm_farm_logs'],
    'data': [
        'security/ir.model.access.csv',
        'views/cultivation_views.xml',
        'views/recipe_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
