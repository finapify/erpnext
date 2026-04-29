from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    finapify_vendor_bank_id = fields.Char(compute='_compute_finapify_vendor_bank_id', string='Finapify Vendor Bank ID')

    def _compute_finapify_vendor_bank_id(self):
        for move in self:
            if move.partner_id and move.company_id:
                m = self.env['finapify.vendor.bank.map'].search([
                    ('company_id','=', move.company_id.id),
                    ('partner_id','=', move.partner_id.id),
                ], limit=1)
                move.finapify_vendor_bank_id = m.finapify_vendor_bank_id if m else False
            else:
                move.finapify_vendor_bank_id = False

    def action_finapify_pay(self):
        """Action to pay the vendor bill via Finapify.
        If draft, it posts the bill first.
        """
        self.ensure_one()
        if self.move_type not in ('in_invoice', 'in_refund'):
            raise UserError(_('Pay with Finapify is only available for vendor bills.'))

        if self.state == 'draft':
            self.action_post()

        if self.state != 'posted':
            raise UserError(_('Bill must be posted before payment.'))

        return {
            'name': _('Pay with Finapify'),
            'type': 'ir.actions.act_window',
            'res_model': 'finapify.pay.single.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': self.id,
                'active_model': 'account.move',
                'default_vendor_bill_id': self.id,
            }
        }
