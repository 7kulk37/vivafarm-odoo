# -*- coding: utf-8 -*-
"""Vivafarm Petty Cash — withdrawal (ใบเบิกเงินสดย่อย) model.

Completes the PNK A.1–A.4 set: A.1 ใบสำคัญจ่าย, A.2 ใบสำคัญรับ,
A.3 ใบสำคัญทั่วไป (all in fund.py), A.4 ใบเบิกเงินสดย่อย (this file).

The withdrawal is the paper form the custodian fills to withdraw cash
from the main cashier/bank to top up the petty cash float. It is a
PURE PAPER FORM for MVP — the top-up wizard (wizard.py) posts the
actual journal entry (Dr 111102 / Cr 111203); the paper trail and the
posting stay separate until a real case needs them linked.
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class VivafarmPettyCashWithdrawal(models.Model):
    _name = 'vivafarm.petty.cash.withdrawal'
    _description = 'Petty Cash Withdrawal (ใบเบิกเงินสดย่อย)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'

    name = fields.Char(
        string='Withdrawal Number',
        required=True,
        default=lambda self: _('New'),
        readonly=True,
    )
    fund_id = fields.Many2one(
        'vivafarm.petty.cash.fund',
        string='Fund',
        required=True,
        ondelete='restrict',
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='fund_id.currency_id',
    )
    purpose = fields.Text(
        string='Purpose',
        required=True,
        help='Why the cash is being withdrawn (e.g. "Top up float for weekly expenses")',
    )
    requested_by = fields.Many2one(
        'res.partner',
        string='Requested By',
        help='The custodian requesting the cash',
    )
    state = fields.Selection(
        [('draft', 'Draft'),
         ('approved', 'Approved'),
         ('paid', 'Paid'),
         ('cancelled', 'Cancelled')],
        string='Status',
        default='draft',
        tracking=True,
    )
    amount_words_th = fields.Char(
        string='Amount in Thai Words',
        compute='_compute_amount_words',
    )
    amount_words_en = fields.Char(
        string='Amount in English Words',
        compute='_compute_amount_words',
    )

    @api.depends('amount', 'currency_id')
    def _compute_amount_words(self):
        """Amount spelled out for the printed form (ตัวอักษร).

        Same pattern as the voucher: Thai via currency.amount_to_text
        with a th_TH context; English is the default.
        """
        for w in self:
            try:
                w.amount_words_th = w.currency_id.with_context(
                    lang='th_TH').amount_to_text(w.amount)
            except Exception:
                w.amount_words_th = False
            try:
                w.amount_words_en = w.currency_id.amount_to_text(w.amount)
            except Exception:
                w.amount_words_en = False

    _withdrawal_name_unique = models.Constraint(
        'UNIQUE(name)',
        'Withdrawal number must be unique.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'vivafarm.petty.cash.withdrawal'
                ) or _('New')
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for w in self:
            if w.amount <= 0:
                raise ValidationError(_('Withdrawal amount must be positive.'))

    def _get_thai_date_display(self, field_name):
        """Date in Thai style: '15/ม.ค./2570' (Buddhist Era year = CE + 543).

        Same helper as the voucher — Babel has no Buddhist calendar
        engine, so compute day/month via the Thai locale (dd/MMM ->
        '15/ม.ค.') and append the Buddhist Era year.
        """
        self.ensure_one()
        value = self[field_name]
        if not value:
            return ''
        from odoo.tools.misc import format_date
        day_month = format_date(self.env, value, lang_code='th_TH', date_format='dd/MMM')
        return '%s/%s' % (day_month, value.year + 543)

    def action_approve(self):
        for w in self:
            if w.state != 'draft':
                continue
            w.write({'state': 'approved'})
        return True

    def action_pay(self):
        for w in self:
            if w.state != 'approved':
                continue
            w.write({'state': 'paid'})
        return True

    def action_cancel(self):
        for w in self:
            w.write({'state': 'cancelled'})
        return True

    def action_draft(self):
        for w in self:
            w.write({'state': 'draft'})
        return True
