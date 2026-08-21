{
    'name': 'VivaFarm Payment Evidence',
    'version': '19.0.1.0.2',
    'category': 'Accounting/Payments',
    'summary': 'Customer uploads payment evidence on the Wire Transfer pay page',
    'description': """
VivaFarm Payment Evidence
==========================
Adds an upload box next to the QR code on the Wire Transfer (payment_custom)
payment status page. The customer uploads their bank transfer slip (PDF/PNG/JPG)
as evidence of payment.

Basic check for a real paid transaction:
- File type must be PDF, PNG, JPG or JPEG; max 10 MB.
- PDFs are text-extracted (pdftotext): if the invoice reference or the
  transaction amount appears in the text, the evidence is auto-validated.
- Images and PDFs without a matching reference/amount go to "Pending Review"
  for the seller to check visually.

Seller side: evidence records are listed under Accounting > Payments > Payment
Evidence and via a smart button on the payment transaction form. The seller can
validate or reject each upload. Evidence is never a blocker: the seller's
confirmation of the wire transfer remains the authoritative payment record.
""",
    'depends': ['payment', 'payment_custom', 'portal', 'vivafarm_document_sign'],
    'data': [
        'security/ir.model.access.csv',
        'views/evidence_views.xml',
        'views/evidence_templates.xml',
        'data/viva_email_template_manual_upload_slip.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
