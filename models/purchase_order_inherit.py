import frappe
from frappe import _

try:
    from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder
    _base = PurchaseOrder
except ImportError:
    from frappe.model.document import Document
    _base = Document


class FinapifyPurchaseOrder(_base):
    """Extends Purchase Order with Finapify payment action."""

    def action_finapify_pay(self):
        if self.status not in ('To Receive and Bill', 'To Bill', 'Completed'):
            frappe.throw(_('Purchase order must be confirmed before payment.'))

        invoices = frappe.get_list(
            'Purchase Invoice',
            filters={
                'purchase_order': self.name,
                'docstatus': ['!=', 2],
            },
            fields=['name', 'docstatus', 'outstanding_amount'],
            order_by='creation desc',
        )

        invoice = None

        if not invoices:
            if self.billing_status == 'Not Billed':
                frappe.throw(_('There is nothing to invoice for this purchase order.'))
            self.make_purchase_invoice()
            invoices = frappe.get_list(
                'Purchase Invoice',
                filters={'purchase_order': self.name, 'docstatus': 0},
                fields=['name', 'docstatus', 'outstanding_amount'],
                limit=1,
            )

        for inv in invoices:
            if inv.docstatus == 0:
                invoice_doc = frappe.get_doc('Purchase Invoice', inv.name)
                invoice_doc.submit()
                invoice = invoice_doc
                break
            if inv.docstatus == 1 and inv.outstanding_amount > 0:
                invoice = frappe.get_doc('Purchase Invoice', inv.name)
                break

        if not invoice:
            frappe.throw(_('No outstanding invoice found to pay, and nothing to invoice.'))

        return {
            'doctype': 'Finapify Pay Single Wizard',
            'new_doc': True,
            'context': {
                'vendor_bill': invoice.name,
                'vendor': invoice.supplier,
                'amount': invoice.outstanding_amount,
                'currency': invoice.currency,
            },
        }
