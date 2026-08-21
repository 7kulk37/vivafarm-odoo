{
    'name': 'VivaFarm Document Sign',
    'version': '19.0.1.0.17',
    'category': 'Accounting/Localizations',
    'summary': 'Thai tax invoice digital integrity: SHA-256 + RSA signature + lock + QR verification',
    'description': """
        Evidence layer for Thai tax invoices (ป.86/2542 + ETA B.E. 2544).

        - Sign a posted tax invoice: render PDF once, SHA-256, RSA sign with
          the configured signing backend (PoC: /etc/odoo/pki/ test CA; later:
          Thai CA cert / PKCS#11 token via the same interface).
        - Lock the signed invoice at ORM level: financial fields + reset-to-
          draft are rejected. The only correction path stays the legal one —
          void + re-issue with a new number (ป.86/2542 ข้อ 25).
        - Revision chain: re-issued invoices become Rev 2+ with
          previous_document_hash linking back (tamper-evident).
        - Public /v/<token> verification page: hash check + upload-compare —
          no Odoo login required.
        - Append-only audit trail (viva.document.audit).

        TEST / NON-PRODUCTION certificate by default. Production = swap the
        cert files / backend provider, no schema change.
    """,
    'depends': ['account', 'sale', 'vivafarm_report'],
    'data': [
        'security/ir.model.access.csv',
        'views/signed_document_views.xml',
        'views/sign_wizard_views.xml',
        'views/report_viva_sign_stamp.xml',
        'views/verification_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
