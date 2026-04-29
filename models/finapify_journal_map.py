from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FinapifyJournalMap(models.Model):
    _name = 'finapify.journal.map'
    _description = 'Finapify Bank ID to Odoo Journal Mapping'
    _rec_name = 'finapify_source_bank_id'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    finapify_source_bank_id = fields.Char(string='Finapify Source Bank ID', required=True)
    journal_id = fields.Many2one(
        'account.journal',
        required=True,
        domain="[('type','=','bank'),('company_id','=',company_id)]"
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('uniq_bank_company', 'unique(company_id, finapify_source_bank_id)', 'Mapping already exists for this bank ID.'),
    ]

    @api.constrains('finapify_source_bank_id')
    def _check_source_bank_id(self):
        for rec in self:
            if rec.finapify_source_bank_id and len(rec.finapify_source_bank_id.strip()) < 3:
                raise ValidationError(_('Finapify Source Bank ID looks too short.'))
