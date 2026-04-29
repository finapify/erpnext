from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_finapify_pay(self):
        """Action to pay the purchase order via Finapify.
        If no bill exists, it creates one, posts it, and then opens the payment wizard.
        """
        self.ensure_one()
        if self.state not in ('purchase', 'done'):
            raise UserError(_('Purchase order must be confirmed before payment.'))

        # Check if there are already invoices
        invoices = self.invoice_ids.filtered(lambda x: x.state != 'cancel')
        
        if not invoices:
            if self.invoice_status == 'no':
                raise UserError(_('There is nothing to invoice for this purchase order.'))
            
            # Create a new invoice
            res = self.action_create_invoice()
            # The action returns a window action for the new invoice
            invoice_id = res.get('res_id')
            if not invoice_id:
                # If multiple invoices created, pick one or raise
                invoice_id = self.invoice_ids.filtered(lambda x: x.state == 'draft')[:1].id
            
            if not invoice_id:
                raise UserError(_('Could not create an invoice for this purchase order.'))
            
            invoice = self.env['account.move'].browse(invoice_id)
        else:
            # Pick the most relevant one (latest draft or latest posted with residual)
            invoice = invoices.filtered(lambda x: x.state == 'draft')[:1]
            if not invoice:
                invoice = invoices.filtered(lambda x: x.state == 'posted' and x.amount_residual > 0)[:1]
            
            if not invoice:
                if self.invoice_status == 'to invoice':
                    res = self.action_create_invoice()
                    invoice_id = res.get('res_id')
                    if invoice_id:
                        invoice = self.env['account.move'].browse(invoice_id)
                
            if not invoice:
                raise UserError(_('No outstanding invoice found to pay, and nothing to invoice.'))

        # Ensure invoice is posted
        if invoice.state == 'draft':
            invoice.action_post()

        # Open the payment wizard
        return {
            'name': _('Pay with Finapify'),
            'type': 'ir.actions.act_window',
            'res_model': 'finapify.pay.single.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_id': invoice.id,
                'active_model': 'account.move',
                'default_vendor_bill_id': invoice.id,
            }
        }
