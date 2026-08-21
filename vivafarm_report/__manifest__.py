{
    'name': 'VivaFarm Report Enhancements',
    "version": "19.0.1.0.159",
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
    'depends': ['l10n_th', 'account', 'sale', 'sale_stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/report_external_layout_viva.xml',
        'data/report_layout_data.xml',
        'views/res_company_views.xml',
        'views/report_viva_invoice.xml',
        'views/report_viva_invoice_plain.xml',
        'views/report_viva_receipt.xml',
        'views/report_viva_credit_note.xml',
        'views/report_viva_debit_note.xml',
        'views/report_viva_delivery_note.xml',
        'views/report_viva_purchase_order.xml',
        'views/report_viva_quotation_so.xml',
        'data/viva_email_template_sent_quotation.xml',
        'data/viva_email_template_order_confirmation.xml',
        'data/viva_email_template_ship_delivery.xml',
        'data/viva_email_template_invoice_acknowledgment.xml',
        'data/viva_email_template_payment_receipt.xml',
        'data/viva_email_template_delivery_acknowledgment.xml',
        'views/stock_picking_ship_dn_button.xml',
        'views/sale_order_sent_quotation_button.xml',
        'views/sale_order_portal_button.xml',
        'views/sale_order_portal_accept_viva_button.xml',
        'views/sale_order_portal_viva_delivery_buttons.xml',
        'views/sale_order_portal_viva_invoice_details.xml',
        'views/account_portal_viva_invoice_buttons.xml',
        'views/report_viva_wht_certificate.xml',
        'views/report_asset_override.xml',
        'views/account_move_views.xml',
        'views/reissue_warning_views.xml',
        'views/default_report_unify.xml',
        'views/report_tax_register.xml',
        'views/report_vat30.xml',
        'views/report_pnd53.xml',
        'views/report_pnd3.xml',
        'views/report_pnd1.xml',
        'views/report_pnd50.xml',
        'views/tax_report_wizard_views.xml',
        'views/cost_of_cultivation_wizard_views.xml',
        'views/report_cost_of_cultivation.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'assets': {
        'web.assets_frontend': [
            'vivafarm_report/static/src/js/accept_viva_guard.js',
            'vivafarm_report/static/src/js/accept_viva_signature_form.js',
            'vivafarm_report/static/src/xml/accept_viva_signature_form.xml',
        ],
    },
}
