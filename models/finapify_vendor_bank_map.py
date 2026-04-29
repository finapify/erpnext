from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FinapifyVendorBankMap(models.Model):
    _name = 'finapify.vendor.bank.map'
    _description = 'Finapify Vendor Bank Mapping'
    _rec_name = 'partner_id'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', required=True, domain=[('supplier_rank', '>', 0)])

    finapify_vendor_bank_id = fields.Char(string='Finapify Vendor Bank ID', required=True)
    verified = fields.Boolean(default=False)
    notes = fields.Text()

    _sql_constraints = [
        ('uniq_vendor_company', 'unique(company_id, partner_id)', 'Only one mapping per vendor and company.'),
    ]

    @api.constrains('finapify_vendor_bank_id')
    def _check_bank_id(self):
        for rec in self:
            if rec.finapify_vendor_bank_id and len(rec.finapify_vendor_bank_id.strip()) < 3:
                raise ValidationError(_('Finapify Vendor Bank ID looks too short.'))
