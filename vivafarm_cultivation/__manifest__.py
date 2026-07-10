{
    'name': 'Hydroponic',
    'version': '1.7.0',
    'category': 'Manufacturing/Agriculture',
    'summary': 'Hydroponic farm management - cultivation, recipes, logs, and material transformation',
    'description': """\
        Complete hydroponic farm operations for leafy green production.

        - Crop Recipes: define seed-to-harvest conversion templates
        - Consumable Recipes: define stock-to-buffer conversion templates
        - Cultivation: seed → live → harvest in one record with status tracking
        - Material Transformation: convert raw materials to intermediate products
        - Farm Input Log: daily EC/pH readings per bench
        - Farm Worker Log: worker activity records with GAP compliance
        - Seed Lot tracking on stock lots for full traceability
    """,
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/cultivation_views.xml',
        'views/recipe_views.xml',
        'views/consumable_recipe_views.xml',
        'views/material_transformation_views.xml',
        'views/farm_input_log_views.xml',
        'views/farm_worker_log_views.xml',
        'views/stock_lot_views.xml',
        'views/farm_location_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
