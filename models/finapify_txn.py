from odoo import fields, models


class FinapifyTxn(models.Model):
    _name = 'finapify.txn'
    _description = 'Finapify Transaction Reference (Idempotency)'
    _rec_name = 'finapify_ref'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    finapify_ref = fields.Char(required=True, index=True)

    request_model = fields.Char()
    request_id = fields.Integer()

    payment_ids = fields.Many2many('account.payment', string='Created Payments')

    _sql_constraints = [
        ('uniq_company_ref', 'unique(company_id, finapify_ref)', 'Transaction already processed.'),
    ]
