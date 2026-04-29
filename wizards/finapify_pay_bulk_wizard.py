from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FinapifyPayBulkWizard(models.TransientModel):
    _name = 'finapify.pay.bulk.wizard'
    _description = 'Bulk Pay Vendor Bills with Finapify'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    mode = fields.Selection([('one_bank','One bank'),('multi_bank','Multi bank')], default='one_bank', required=True)
    source_bank_id = fields.Char(string='Default Payer Bank ID')

    otp = fields.Char(string='OTP', required=True)

    bill_ids = fields.Many2many('account.move', string='Vendor Bills', required=True)

    def _get_active_bills(self):
        ids = self.env.context.get('active_ids') or []
        bills = self.env['account.move'].browse(ids).exists()
        bills = bills.filtered(lambda m: m.move_type in ('in_invoice','in_refund'))
        return bills

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        bills = self._get_active_bills()
        if bills:
            res['company_id'] = bills[0].company_id.id
            res['bill_ids'] = [(6, 0, bills.ids)]

            conn = self.env['finapify.connection'].search([
                ('company_id','=', bills[0].company_id.id),
                ('user_id','=', self.env.user.id),
            ], limit=1)
            if conn and conn.default_source_bank_id:
                res['source_bank_id'] = conn.default_source_bank_id
        return res

    def action_pay_bulk(self):
        self.ensure_one()
        bills = self.bill_ids
        if not bills:
            raise UserError(_('Select at least one vendor bill.'))
        if len(set(bills.mapped('company_id').ids)) > 1:
            raise UserError(_('All selected bills must belong to the same company.'))

        # validate
        for b in bills:
            if b.state != 'posted':
                raise UserError(_("Bill %s must be posted.") % b.display_name)
            if b.amount_residual <= 0:
                raise UserError(_("Bill %s has no residual.") % b.display_name)

        batch = self.env['finapify.payment.batch'].create({
            'company_id': bills[0].company_id.id,
            'mode': self.mode,
            'source_bank_id': self.source_bank_id,
            'currency_id': bills[0].currency_id.id,
            'otp_required': True,
            'status': 'otp_pending',
        })

        # create lines
        for b in bills:
            m = self.env['finapify.vendor.bank.map'].search([
                ('company_id','=', b.company_id.id),
                ('partner_id','=', b.partner_id.id),
            ], limit=1)
            if not m:
                raise UserError(_("Missing Finapify Vendor Bank ID for vendor: %s") % b.partner_id.name)

            # choose source bank per line
            sb = self.source_bank_id
            if not sb:
                raise UserError(_('Select a payer bank id.'))

            self.env['finapify.payment.batch.line'].create({
                'batch_id': batch.id,
                'vendor_bill_id': b.id,
                'amount': b.amount_residual,
                'currency_id': b.currency_id.id,
                'vendor_bank_id': m.finapify_vendor_bank_id,
                'source_bank_id': sb,
                'status': 'pending',
            })

        batch.write({'bill_ids': [(6, 0, bills.ids)]})
        batch.action_submit_to_n8n(self.otp)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Finapify Payment Batch'),
            'res_model': 'finapify.payment.batch',
            'res_id': batch.id,
            'view_mode': 'form',
            'target': 'current',
        }
