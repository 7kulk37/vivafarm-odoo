{
    'name': 'VivaFarm Report Enhancements',
    'version': '19.0.1.0.57',
    'category': 'Accounting/Localizations',
    'summary': 'Thai invoice compliance: signature image, branch info, tax breakdown on invoice report',
    'description': """
        Thai Tax Invoice compliance enhancements for VivaFarm hydroponic farm.

        - Company signature image field (ลายมือชื่อผู้มีอำนาจลงนาม)
        - Company branch name field (สาขา)
        - QWeb template extension to render signature + branch on Thai Tax Invoice
        - Tax amount breakdown shown separately on invoice
        - Unified default-report address pattern: customer LEFT, shipping RIGHT
          (when separate), invoice address hidden (default_report_unify.xml)
    """,
    'depends': ['l10n_th', 'account'],
    'data': [
        'views/report_external_layout_viva.xml',
        'data/report_layout_data.xml',
        'views/res_company_views.xml',
        'views/report_viva_invoice.xml',
        'views/account_move_views.xml',
        'views/default_report_unify.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
