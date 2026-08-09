from odoo import _, api, fields, models
from odoo.exceptions import UserError

#: Maximum number of product line items that fit on a single A4 sheet for the
#: VivaFarm tax invoice. Calibrated on staging with the real business layout
#: (exempt 0% VAT, 30-day payment term, no discounts): the ending block
#: (totals + payment + T&C + signatures) measures ~309pt and each product row
#: ~26.2pt. Reference geometry (margin_top 107mm) leaves ~4 lines per sheet:
#: 4-line sig ends 739pt + date row ~770pt fits (789pt usable), 5-line
#: sig 767pt + date row ~798pt overflows. Only product lines count —
#: sections/notes share a row.
MULTIPAGE_PRODUCT_LINES = 5


class AccountMove(models.Model):
    _inherit = 'account.move'

    #: Original tax invoice this document was re-issued to replace (Thai
    #: Revenue Code ป.86/2542 ข้อ 25(2)/(3)): when a posted tax invoice has
    #: essential elements wrong, it must be voided and a NEW invoice issued
    #: with a NEW number and the SAME date, carrying the note "เป็นการยกเลิก
    #: และออกใบกำกับภาษีฉบับใหม่แทนฉบับเดิมเลขที่ ...". The report renders
    #: that note from this field (full-width, wraps freely — unlike `ref`,
    #: which ellipsizes inside the header frame).
    replacement_of_id = fields.Many2one(
        'account.move', string='Replaces Invoice', ondelete='set null',
        help="Original tax invoice this document was re-issued to replace (ป.86/2542 ข้อ 25).")

    #: Root of the re-issue chain (ป.86/2542 ข้อ 25). Every member of a chain
    #: (the voided original and each re-issued replacement) carries the id of
    #: the chain ROOT. Stored so the re-issue history is searchable — the
    #: 'Re-issued' stat button on the invoice form lists every member, and
    #: reissue_count shows how many times the chain has been re-issued.
    reissue_root_id = fields.Many2one(
        'account.move', string='Re-issue Chain Root', index=True, ondelete='set null')

    #: Number of re-issues in this move's chain (excluding the original).
    #: Non-stored: recomputed on access for the stat button / warning wizard.
    reissue_count = fields.Integer(
        compute='_compute_reissue_count', string='Times Re-issued')

    @api.depends('reissue_root_id')
    def _compute_reissue_count(self):
        for move in self:
            root = move.reissue_root_id or move.id
            members = self.search([('reissue_root_id', '=', root)])
            move.reissue_count = max(0, len(members) - 1)

    def _get_reissue_chain(self):
        """All moves in this move's re-issue chain (root + replacements).

        The chain root is the ORIGINAL tax invoice; every replacement (and
        the root itself) carries the same reissue_root_id, so the chain is a
        flat search — no recursive walk needed. Returns records ordered by
        id (chronological). If this move is not part of a chain, returns
        just itself.
        """
        self.ensure_one()
        root = self.reissue_root_id or self
        return self.search([('reissue_root_id', '=', root.id)])

    def _is_multipage(self):
        """Whether this tax invoice spans more than one sheet per copy.

        Thai Revenue Code practice (ป.86/2542 ข้อ 9(2)): when the line-item
        table cannot fit on one sheet, the invoice continues on further
        sheets — each sheet repeats elements (1)-(5),(7), totals appear only
        on the last sheet, and non-final sheets carry a continuation note.
        The report uses this flag to show the continuation note (tfoot) and
        to keep the ending block on the last sheet.

        The ending block (totals + payment + T&C + signatures) is taller when
        the totals table carries extra rows: each VAT/exempt row beyond the
        baseline tax row adds height. Every extra row consumes ~1 product-line
        equivalent (~26pt), so they count toward the single-sheet capacity.
        (Discounts are never shown on the invoice — pricelist-only pricing —
        so they add no rows.)

        Product rows are also taller when the line name wraps: each embedded
        newline adds a text line (~26pt), e.g. names built from product
        internal reference + name ('[TRIM-001] Gasoline Grass Trimmer\n...')
        render two lines per row.
        """
        self.ensure_one()
        if self.move_type != 'out_invoice':
            return False
        product_lines = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        tt = self._get_tax_invoice_totals()
        extra_rows = 0
        # Baseline totals table always has exactly one tax row (VAT or
        # VAT-exempt); only rows beyond that add height.
        extra_rows += max(0, len(tt['vat_rows']) + len(tt['exempt_rows']) - 1)
        # Multi-line product names: each embedded newline adds a text line.
        wrapped_lines = sum(max(0, (l.name or '').count('\n'))
                            for l in product_lines)
        effective_lines = len(product_lines) + extra_rows + wrapped_lines
        if effective_lines >= MULTIPAGE_PRODUCT_LINES:
            return True
        # A long description (>30 newlines) can make the line-item table span
        # pages even with few lines — mirror the template's has_long_desc
        # heuristic so the continuation note + grouped ending still apply.
        return any(line.name and line.name.count('\n') > 30
                   for line in self.invoice_line_ids if line.name)

    def _get_thai_date_display(self, field_name):
        """Date in Thai tax-invoice style: '03/ส.ค./2569' (Buddhist Era year = CE + 543).

        Babel has no Buddhist calendar engine, so the TH report computes the
        day/month via the Thai locale (dd/MMM -> '03/ส.ค.') and appends the
        Buddhist Era year (Gregorian year + 543).
        """
        self.ensure_one()
        value = self[field_name]
        if not value:
            return ''
        from odoo.tools.misc import format_date
        day_month = format_date(self.env, value, lang_code='th_TH', date_format='dd/MMM')
        return '%s/%s' % (day_month, value.year + 543)

    def _get_tax_invoice_copies(self):
        """Copies to print for a tax invoice (Thai practice: 3 copies).

        Only posted customer invoices (ใบกำกับภาษี) print 3 copies; all other
        documents print a single copy without the copy badge.
        """
        self.ensure_one()
        if self.move_type == 'out_invoice' and self.state == 'posted':
            return [
                {'key': 'original', 'th_marker': 'ต้นฉบับ', 'en_marker': 'Original', 'th_recipient': 'สำหรับลูกค้า', 'en_recipient': 'For Customer'},
                {'key': 'company',  'th_marker': 'สำเนา',   'en_marker': 'Copy',     'th_recipient': 'สำหรับบริษัท', 'en_recipient': 'For Company'},
                {'key': 'account',  'th_marker': 'สำเนา',   'en_marker': 'Copy',     'th_recipient': 'สำหรับบัญชี', 'en_recipient': 'For Accounting'},
            ]
        return [{'key': False, 'th_marker': '', 'en_marker': '', 'th_recipient': '', 'en_recipient': ''}]

    def _get_credit_note_copies(self):
        """Copies to print for a credit note (ใบลดหนี้): 3 copies.

        Matches the tax invoice triplicate: ต้นฉบับ/สำหรับลูกค้า (Original /
        For Customer) + สำเนา/สำหรับบริษัท (Copy / For Company) + สำเนา/
        สำหรับบัญชี (Copy / For Accounting). Only posted customer credit
        notes (out_refund) print 3 copies.
        """
        self.ensure_one()
        if self.move_type == 'out_refund' and self.state == 'posted':
            return [
                {'key': 'original', 'th_marker': 'ต้นฉบับ', 'en_marker': 'Original', 'th_recipient': 'สำหรับลูกค้า', 'en_recipient': 'For Customer'},
                {'key': 'company',  'th_marker': 'สำเนา',   'en_marker': 'Copy',     'th_recipient': 'สำหรับบริษัท', 'en_recipient': 'For Company'},
                {'key': 'account',  'th_marker': 'สำเนา',   'en_marker': 'Copy',     'th_recipient': 'สำหรับบัญชี', 'en_recipient': 'For Accounting'},
            ]
        return [{'key': False, 'th_marker': '', 'en_marker': '', 'th_recipient': '', 'en_recipient': ''}]

    def _get_tax_invoice_totals(self):
        """Rows for the Thai tax-invoice totals table (bilingual).

        Follows Thai practice (RD sec. 86/4 + common layouts, cf. the
        reference invoice): TOTAL AMOUNT, DISCOUNT (when any), VAT rows with
        rate (or an explicit VAT-exempt line), GRAND TOTAL.

        Withholding-tax groups are excluded: WHT is an income-tax matter
        handled by the buyer with a separate certificate, never shown on a
        seller's VAT tax invoice.

        Discounts are never shown on the invoice: VivaFarm pricing is
        pricelist-only (no manual per-line discounts), and a pricelist
        discount is already reflected in the lower selling price. The line
        table shows the effective (discounted) unit price and the totals
        table has no Discount / Total After Discount rows.

        price_subtotal is the pre-tax, post-discount line amount (VAT is
        already extracted for price-included taxes), so it is the gross
        shown as Total Amount. This keeps the rows reconciling:
        Total Amount + VAT = Grand Total. (Previously gross_total used
        price_unit * qty, which for price-included VAT included the tax and
        made Total Amount equal Grand Total.)
        """
        self.ensure_one()
        tt = self.tax_totals or {}
        lines = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        gross_total = sum(l.price_subtotal for l in lines)
        discount = 0.0
        net_total = tt.get('base_amount_currency', gross_total)
        vat_rows = []
        exempt_rows = []
        for subtotal in tt.get('subtotals') or []:
            for group in subtotal.get('tax_groups') or []:
                taxes = self.env['account.tax'].browse(group.get('involved_tax_ids') or [])
                # Withholding-tax groups carry NEGATIVE tax amounts (e.g.
                # '1% WH T' = -1.0). Detect by sign, NOT by group name — names
                # are translated (th_TH: 'หัก ณ ที่จ่าย 1%'), so a substring
                # check behaves differently per language (EN hid the 0% EXEMPT
                # row while TH showed it). 0% EXEMPT (amount 0.0) must NOT be
                # skipped even if it sits in a WHT-named group (data drift).
                if taxes and any(t.amount < 0 for t in taxes):
                    continue  # withholding tax: not shown on a VAT tax invoice
                label = ', '.join(t.name for t in taxes) or group.get('group_name') or ''
                amount = group.get('tax_amount_currency') or 0.0
                if amount:
                    rate = max((t.amount for t in taxes if t.amount_type in ('percent', 'division')),
                               default=None)
                    vat_rows.append({'rate_label': ('%g%%' % rate) if rate is not None else '',
                                     'amount': amount})
                elif label:
                    exempt_rows.append({'label': label})
        return {
            'gross_total': gross_total,
            'discount': discount,
            'net_total': net_total,
            'vat_rows': vat_rows,
            'exempt_rows': exempt_rows,
            'is_exempt': not vat_rows,
            'grand_total': tt.get('total_amount_currency', net_total),
        }

    @api.depends('restrict_mode_hash_table', 'state', 'inalterable_hash', 'posted_before')
    def _compute_show_reset_to_draft_button(self):
        """Hide 'Reset to Draft' on posted-then-cancelled customer invoices.

        Thai Revenue Code ป.86/2542 ข้อ 25(2): a replacement tax invoice must
        carry a NEW number. Odoo's reset-to-draft on a posted-then-cancelled
        invoice reuses the same number on re-post — the exact situation the
        rule forbids. Hide the button there; the 'Re-issue' button
        (action_reissue) provides the compliant path instead. Draft invoices
        that were cancelled (never posted, no number consumed) keep the
        standard button — resetting them is harmless. Vendor bills and
        journal entries keep standard Odoo behaviour.
        """
        super()._compute_show_reset_to_draft_button()
        for move in self:
            if (move.move_type == 'out_invoice' and move.state == 'cancel'
                    and move.posted_before):
                move.show_reset_to_draft_button = False

    def action_open_reissue_chain(self):
        """Open the list of all invoices in this move's re-issue chain.

        Shows the original + every replacement so the full mistake trail is
        visible from any member (not just the last re-issue).
        """
        self.ensure_one()
        chain = self._get_reissue_chain()
        return {
            'name': _('Re-issue Chain'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', chain.ids)],
            'context': {'create': False, 'delete': False},
        }

    def button_reissue(self):
        """Entry point for the 'Re-issue' button.

        First re-issue in a chain: perform it immediately (single click).
        Any further re-issue in the same chain: open a soft-warning wizard
        first so the user consciously confirms the extra mistake trail.
        """
        self.ensure_one()
        chain = self._get_reissue_chain()
        # chain includes the original; reissue_count = members - 1.
        # If this move is itself a replacement (or the original already
        # re-issued once), a re-issue here is 2nd+ in the chain.
        is_first = self.reissue_count == 0
        if is_first:
            return self.action_reissue()
        return {
            'name': _('Re-issue Confirmation'),
            'type': 'ir.actions.act_window',
            'res_model': 'reissue.warning',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
                'default_reissue_count': self.reissue_count,
            },
        }

    def action_reissue(self):
        """Compliant re-issue of a voided tax invoice (ป.86/2542 ข้อ 25).

        Called from the 'Re-issue' button on a posted-then-cancelled customer
        invoice. Copies the voided invoice, keeps the original invoice date
        (ข้อ 25(2) — the replacement is dated the same day), links it via
        replacement_of_id so the report prints the 'ออกแทนใบกำกับภาษีฉบับเดิม
        เลขที่ ...' note (ข้อ 25(3)), and posts it to consume a fresh number.

        :return: action opening the new invoice's form view.
        """
        self.ensure_one()
        if not (self.move_type == 'out_invoice' and self.state == 'cancel'
                and self.posted_before):
            raise UserError(
                _("Re-issue is only available on a cancelled customer invoice "
                  "that was previously posted."))
        # Guard against accidental double re-issue: this was originally a
        # hard UserError, but the soft-warning wizard (button_reissue) now
        # gates every 2nd+ re-issue in a chain, so the hard block is
        # redundant and would prevent the legitimate warned re-issue.
        # The wizard's confirm is the only way to reach here for 2nd+.
        new_invoice = self.with_context(
            include_business_fields=True,
            skip_invoice_sync=self.move_type == 'entry',
        ).copy({
            'replacement_of_id': self.id,
            # Chain root: the root of THIS move's chain (or itself when
            # this is the original). Every replacement joins the same
            # chain so the full history is searchable via reissue_root_id.
            'reissue_root_id': self.reissue_root_id.id or self.id,
        })
        new_invoice.write({
            'invoice_date': self.invoice_date,
            'date': self.invoice_date or self.date,
            'ref': False,
        })
        new_invoice.action_post()
        return {
            'name': _('Re-issued Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': new_invoice.id,
            'view_mode': 'form',
        }
