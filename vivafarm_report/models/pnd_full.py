from odoo import api, models
from odoo.tools import format_amount
from odoo.tools.misc import format_date


class ReportPndFull(models.AbstractModel):
    """Data model for the combined ภ.ง.ด.3/53 PDF: cover page (official
    layout) + ใบแนบ schedule page (S6+S7).

    Values are re-used from the existing PND data models so the cover's
    summary lines and the ใบแนบ totals are computed from the SAME posted
    lines (P6 — single source of truth) and always tie.
    """

    _name = 'report.vivafarm_report.report_pnd3_full'
    _description = 'Thai PND Full (Cover + ใบแนบ) Data'

    def _cover_vals(self, wizard, pnd_type):
        """Compute cover values from the existing PND report model."""
        pnd_model = self.env[
            'report.vivafarm_report.report_pnd3' if pnd_type == 'pnd3'
            else 'report.vivafarm_report.report_pnd53']
        vals = pnd_model._get_report_values(wizard.ids)
        company = self.env.company
        addr = ' '.join(x for x in (
            company.street, company.street2, company.city or '', company.zip or ''
        ) if x)
        thai_month = format_date(
            self.env, wizard.date_from, lang_code='th_TH', date_format='MMMM')
        thai_year = wizard.date_from.year + 543
        # ใบแนบ counts from the attach model
        attach = self.env['report.vivafarm_report.report_wht_attach']
        avals = attach._get_report_values(wizard.ids, {'pnd_type': pnd_type})
        return {
            'cover_company': company,
            'cover_address': addr,
            'thai_month': thai_month,
            'thai_year': thai_year,
            'cover_total_income': vals['total_income'],
            'cover_total_remit': vals['total_remit'],
            'cover_surcharge': vals['surcharge'],
            'cover_total': vals['total'],
            'attach_rows': avals['n_rows'],
            'attach_sheets': avals['n_sheets'],
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['tax.report.wizard'].browse(docids)
        pnd_type = (data or {}).get('pnd_type') or (
            'pnd3' if wizard.register_type == 'pnd3' else 'pnd53')
        cover = self._cover_vals(wizard, pnd_type)
        # Expose the ใบแนบ values in the same render context (the wrapper
        # template t-calls report_wht_attach which re-reads these globals).
        attach = self.env['report.vivafarm_report.report_wht_attach']
        avals = attach._get_report_values(wizard.ids, {'pnd_type': pnd_type})
        out = {
            'doc_ids': wizard.ids,
            'doc_model': self._name,
            'docs': wizard,
            'pnd_type': pnd_type,
        }
        out.update(cover)
        out.update({k: v for k, v in avals.items()
                    if k not in ('doc_ids', 'doc_model', 'docs')})
        return out


class ReportPnd53Full(models.AbstractModel):
    _name = 'report.vivafarm_report.report_pnd53_full'
    _description = 'Thai PND53 Full (Cover + ใบแนบ) Data'
    _inherit = 'report.vivafarm_report.report_pnd3_full'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        data['pnd_type'] = 'pnd53'
        return super()._get_report_values(docids, data)