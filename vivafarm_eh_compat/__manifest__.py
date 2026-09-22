{
    'name': 'VivaFarm EH Compatibility Fixes',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Upstream-bug workarounds for ERP Heritage modules (no EH code edits)',
    'description': """
VivaFarm EH Compatibility
=========================
Fixes for three upstream ERP Heritage seal-guard bugs, implemented entirely in this
custom module (erp-heritage is community code and is never edited):

1. eh.borrowing.cost.action_capitalise — created the sealed journal entry with an
   inline 'eh_sealed': True create, which the eh_account_base create-guard rejects
   (AccessError: "The sub-ledger journal-entry seal is server-owned..."). Overridden
   to create through the sanctioned account.move._eh_create_sealed helper.

2. eh.year.end.run._build_closing_move — same inline-create problem (post fails);
   overridden to use _eh_create_sealed.

3. eh.year.end.run._build_reversal_move — called move._reverse_moves(), blocked by
   the seal guard for sealed moves; overridden to use the sanctioned
   _eh_reverse_sealed_move mixin helper.

These overrides call ONLY the public/sanctioned EH helpers (the same patterns
eh_account_base itself uses); no EH file is modified. If upstream fixes these
methods, this module can be uninstalled and the native paths resume.
""",
    'author': 'VivaFarm',
    'depends': ['eh_account_base', 'eh_account_borrowing_costs', 'eh_account_year_end'],
    'data': [],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}