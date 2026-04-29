from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    finapify_vendor_bank_map_id = fields.Many2one(
        'finapify.vendor.bank.map',
        compute='_compute_finapify_map',
        string='Finapify Bank Mapping'
    )

    def _compute_finapify_map(self):
        for p in self:
            m = self.env['finapify.vendor.bank.map'].search([
                ('company_id','=', self.env.company.id),
                ('partner_id','=', p.id),
            ], limit=1)
            p.finapify_vendor_bank_map_id = m
