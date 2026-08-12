{
    'name': 'VivaFarm GAP Reports',
    'version': '19.0.1.0.21',
    'category': 'Manufacturing/Agriculture',
    'summary': 'Printable GAP audit reports: cultivation record, worker/input logs, material transformation, scrap, petty cash, lot traceability',
    'description': """
        Printable GAP audit reports for VivaFarm hydroponic farm.

        - Cultivation Record (GAP 5.1): seed-to-harvest cycle
        - Worker Daily Log (GAP 5.5, Labor Law 76)
        - Daily Input Log EC/pH (GAP 5.3)
        - Material Transformation Record (GAP 5.2)
        - Scrap Order (spoilage record)
        - Petty Cash Voucher (Thai-compliant)
        - Product Traceability / Lot History (GAP 5.6)

        All reports render on the VivaFarm letterhead (external layout from
        vivafarm_report) with the VivaFarm paperformat.
    """,
    'depends': [
        'hr',
        'vivafarm_cultivation',
        'vivafarm_petty_cash',
        'vivafarm_report',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/training_record_views.xml',
        'views/report_cultivation.xml',
        'views/report_worker_log.xml',
        'views/report_wage_sheet.xml',
        'views/report_input_log.xml',
        'views/report_material_transformation.xml',
        'views/report_scrap.xml',
        'views/report_petty_cash_voucher.xml',
        'views/report_petty_cash_withdrawal.xml',
        'views/report_lot_traceability.xml',
        'views/menu_inventory_valuation.xml',
        'views/report_stock_card.xml',
        'views/report_wht_certificate.xml',
        'views/report_wage_slip.xml',
        'views/report_employee_register.xml',
        'views/report_training_record.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
