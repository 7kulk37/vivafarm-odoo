# -*- coding: utf-8 -*-
"""Upstream-bug workarounds for ERP Heritage seal-guard issues.

erp-heritage (eh_account_* modules) is community code and is NEVER edited.
These overrides live entirely in this custom module. They call the upstream
methods UNCHANGED inside a context that carries the sanctioned eh_account_base
object() capability sentinels (imported by identity — the same corridor pattern
as vivafarm_report's legal-PDF helper). The sentinels are unforgeable through
RPC; only server-side code can pass. If upstream fixes the methods, uninstalling
this module restores the native paths.
"""
from odoo import models

try:
    from odoo.addons.eh_account_base.models.account_move import (
        _EH_ALLOW_SEAL,
        _EH_SEAL_CAPABILITY,
        _EH_REVERSE_SEALED,
        _EH_REVERSE_SEALED_CAPABILITY,
    )
    _EH_CORRIDOR = {
        _EH_ALLOW_SEAL: _EH_SEAL_CAPABILITY,
        _EH_REVERSE_SEALED: _EH_REVERSE_SEALED_CAPABILITY,
    }
except ImportError:  # EH not installed — overrides are inert
    _EH_CORRIDOR = None


class EhBorrowingCost(models.Model):
    """Fix action_capitalise: the inline eh_sealed create is rejected by the
    eh_account_base seal guard. Run the upstream action inside the sanctioned
    seal corridor (context carries the _EH_ALLOW_SEAL capability sentinel).
    """
    _inherit = 'eh.borrowing.cost'

    def action_capitalise(self):
        if _EH_CORRIDOR is None:
            return super().action_capitalise()
        return super(
            EhBorrowingCost,
            self.with_context(**_EH_CORRIDOR),
        ).action_capitalise()


class EhYearEndRun(models.Model):
    """Fix _build_closing_move (inline eh_sealed create rejected) and
    _build_reversal_move (raw _reverse_moves blocked for sealed moves): run
    both upstream methods inside the sanctioned seal/reverse corridor.
    """
    _inherit = 'eh.year.end.run'

    def _build_closing_move(self):
        if _EH_CORRIDOR is None:
            return super()._build_closing_move()
        return super(
            EhYearEndRun,
            self.with_context(**_EH_CORRIDOR),
        )._build_closing_move()

    def _build_reversal_move(self):
        if _EH_CORRIDOR is None:
            return super()._build_reversal_move()
        return super(
            EhYearEndRun,
            self.with_context(**_EH_CORRIDOR),
        )._build_reversal_move()
