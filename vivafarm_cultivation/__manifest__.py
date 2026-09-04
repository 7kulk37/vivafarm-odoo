{
    'name': 'Hydroponic',
    'version': '1.53.0',
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
    'depends': ['stock', 'sale'],
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
        'views/spoilage_disposal_views.xml',
        'views/batch_cost_sheet_report.xml',
        'views/nutrient_mix_views.xml',
        'views/pest_cleaning_views.xml',
        'views/chemical_register_views.xml',
        'views/sale_order_line_views.xml',
        'views/water_test_views.xml',
        'views/cash_accrual_recon_views.xml',
        'views/vat_flip_guard_views.xml',
        'views/year_end_closure_views.xml',
        'views/physical_count_views.xml',
        'views/nrv_guard_views.xml',
        'views/recall_drill_views.xml',
        'views/insurance_policy_views.xml',
        'views/yield_metric_views.xml',
        'views/temperature_log_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
