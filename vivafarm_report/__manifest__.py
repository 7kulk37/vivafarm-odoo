{
    'name': 'VivaFarm Report Enhancements',
    'version': '19.0.1.0.79',
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
        'security/ir.model.access.csv',
        'views/report_external_layout_viva.xml',
        'data/report_layout_data.xml',
        'views/res_company_views.xml',
        'views/report_viva_invoice.xml',
        'views/report_viva_receipt.xml',
        'views/report_viva_credit_note.xml',
        'views/report_asset_override.xml',
        'views/account_move_views.xml',
        'views/default_report_unify.xml',
        'views/report_tax_register.xml',
        'views/report_vat30.xml',
        'views/tax_report_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
