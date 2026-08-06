{
    'name': 'VivaFarm Report Enhancements',
    'version': '19.0.1.0.39',
    'category': 'Accounting/Localizations',
    'summary': 'Thai invoice compliance: signature image, branch info, tax breakdown on invoice report',
    'description': """
        Thai Tax Invoice compliance enhancements for VivaFarm hydroponic farm.

        - Company signature image field (ลายมือชื่อผู้มีอำนาจลงนาม)
        - Company branch name field (สาขา)
        - QWeb template extension to render signature + branch on Thai Tax Invoice
        - Tax amount breakdown shown separately on invoice
    """,
    'depends': ['l10n_th', 'account'],
    'data': [
        'data/report_layout_data.xml',
        'views/res_company_views.xml',
        'views/report_external_layout_viva.xml',
        'views/report_viva_invoice.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
