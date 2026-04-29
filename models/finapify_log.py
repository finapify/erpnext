from odoo import fields, models


class FinapifyLog(models.Model):
    _name = 'finapify.log'
    _description = 'Finapify Audit Log'
    _order = 'timestamp desc, id desc'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    timestamp = fields.Datetime(default=fields.Datetime.now, required=True)
    user_id = fields.Many2one('res.users')

    correlation_id = fields.Char(index=True)
    model = fields.Char()
    record_id = fields.Integer()

    action = fields.Char()
    level = fields.Selection([('info','Info'),('warn','Warn'),('error','Error')], default='info')

    message = fields.Char()
    request_json = fields.Text()
    response_json = fields.Text()
