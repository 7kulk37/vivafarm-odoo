{
    'name': 'VivaFarm Paperless Archive',
    'version': '19.0.1.0.2',
    'category': 'Accounting/Localizations',
    'summary': 'Archive signed & hashed documents into Paperless-ngx (immutable secondary copy)',
    'description': """
        Archive layer for vivafarm_document_sign: every signed/hashed PDF
        (tax invoice, SO, delivery note, receipt, manual upload) is copied
        into Paperless-ngx with Odoo linkage custom fields, and the Paperless
        document ID is recorded back on viva.signed.document.

        - AUTO-UPLOAD on sign (pending -> uploaded via cron retry)
        - EN-first titles: "<Document Type> - <Number> - <Signer>"
        - Search-first adoption: a retry never creates a duplicate Paperless
          doc (custom_field_query on odoo_signed_doc_id)
        - On-demand verify + batch verify + scheduled verify (download back
          from Paperless, SHA-256 compare against the uploaded bytes)
        - FULLY DECOUPLED: vivafarm_document_sign does not depend on this
          module. Uninstall this module or Paperless being down never breaks
          signing — uploads fail into 'failed' and are retried by cron.
    """,
    'depends': ['vivafarm_document_sign'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/paperless_actions.xml',
        'views/signed_document_views.xml',
        'views/paperless_document_views.xml',
        'views/paperless_proof_templates.xml',
        'views/paperless_search_views.xml',
        'views/paperless_incoming_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
