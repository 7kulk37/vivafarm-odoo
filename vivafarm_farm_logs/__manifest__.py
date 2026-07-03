{
    'name': 'VivaFarm Farm Logs',
    'version': '1.1.0',
    'category': 'Manufacturing/Agriculture',
    'summary': 'Daily farm input logs and worker logs for hydroponic GAP compliance',
    'description': """
        Tracks daily farm operations for hydroponic leafy green production.

        - Farm Input Log: daily EC/pH readings per bench with nutrient/acid adjustments
        - Farm Worker Log: worker activity records with safety briefing
        - Seed Lot tracking on stock lots for full seed-to-sale traceability

        Part of the VivaFarm infrastructure for Thai GAP compliance.
    """,
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/farm_input_log_views.xml',
        'views/farm_worker_log_views.xml',
        'views/stock_lot_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}