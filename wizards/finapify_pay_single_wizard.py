from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FinapifyPaySingleWizard(models.TransientModel):
    _name = 'finapify.pay.single.wizard'
    _description = 'Pay Single Vendor Bill with Finapify'

    vendor_bill_id = fields.Many2one('account.move', required=True)
    company_id = fields.Many2one('res.company', related='vendor_bill_id.company_id', store=True)

    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one('res.currency', related='vendor_bill_id.currency_id', store=True)

    source_bank_id = fields.Char(required=True)
    vendor_bank_id = fields.Char(required=True)

    otp = fields.Char(string='OTP', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            bill = self.env['account.move'].browse(active_id)
            res['vendor_bill_id'] = bill.id
            res['amount'] = bill.amount_residual

            # default connection
            conn = self.env['finapify.connection'].search([
                ('company_id','=', bill.company_id.id),
                ('user_id','=', self.env.user.id),
            ], limit=1)
            if conn and conn.default_source_bank_id:
                res['source_bank_id'] = conn.default_source_bank_id

            # vendor mapping
            m = self.env['finapify.vendor.bank.map'].search([
                ('company_id','=', bill.company_id.id),
                ('partner_id','=', bill.partner_id.id),
            ], limit=1)
            if m:
                res['vendor_bank_id'] = m.finapify_vendor_bank_id
        return res

    def action_pay(self):
        self.ensure_one()
        bill = self.vendor_bill_id
        if bill.state != 'posted':
            raise UserError(_('Bill must be posted.'))
        if self.amount <= 0:
            raise UserError(_('Amount must be positive.'))

        # create request
        req = self.env['finapify.payment.request'].create({
            'company_id': bill.company_id.id,
            'vendor_bill_id': bill.id,
            'amount': self.amount,
            'currency_id': bill.currency_id.id,
            'source_bank_id': self.source_bank_id,
            'vendor_bank_id': self.vendor_bank_id,
            'otp_required': True,
            'status': 'otp_pending',
        })

        req.action_submit_to_n8n(self.otp)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Finapify Payment Request'),
            'res_model': 'finapify.payment.request',
            'res_id': req.id,
            'view_mode': 'form',
            'target': 'current',
        }
