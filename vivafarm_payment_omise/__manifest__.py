{
    'name': 'VivaFarm Omise Payment Provider',
    'version': '19.0.1.0.6',
    'category': 'Accounting/Payment',
    'summary': 'Omise payment provider for card and PromptPay (Thailand)',
    'description': """
VivaFarm Omise Payment Provider
===============================
Adds Omise as a payment provider supporting:
- Card payments (pull, gateway-validated)
- PromptPay QR (push, gateway-validated via webhook)

Test mode supported with Omise test keys.
    """,
    'author': 'VivaFarm',
    'website': 'https://vivafarm.local',
    'license': 'LGPL-3',
    'depends': ['payment', 'account_payment'],
    'data': [
        'data/payment_provider_data.xml',
        'data/ir_cron.xml',
        'views/payment_provider_views.xml',
        'views/omise_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'vivafarm_payment_omise/static/src/js/payment_form.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
