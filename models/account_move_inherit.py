import frappe
from frappe import _

try:
    from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import PurchaseInvoice
    _base = PurchaseInvoice
except ImportError:
    from frappe.model.document import Document
    _base = Document


class FinapifyPurchaseInvoice(_base):
    """Extends Purchase Invoice with Finapify payment action."""

    def action_finapify_pay(self):
        if self.move_type not in ('in_invoice', 'in_refund') and self.doctype != 'Purchase Invoice':
            frappe.throw(_('Pay with Finapify is only available for vendor bills.'))

        if self.docstatus == 0:
            self.submit()

        if self.docstatus != 1:
            frappe.throw(_('Bill must be submitted before payment.'))

        return {
            'doctype': 'Finapify Pay Single Wizard',
            'new_doc': True,
            'context': {
                'vendor_bill': self.name,
                'vendor': self.supplier,
                'amount': self.outstanding_amount,
                'currency': self.currency,
            },
        }


@frappe.whitelist()
def get_finapify_payment_info(doctype, name):
    """Return Finapify vendor bank map info for a Purchase Invoice."""
    doc = frappe.get_doc(doctype, name)
    supplier = getattr(doc, 'supplier', None) or getattr(doc, 'party', None)
    if not supplier:
        return {}

    bank_map = frappe.db.get_value(
        'Finapify Vendor Bank Map',
        {'supplier': supplier},
        ['finapify_vendor_bank_id', 'verified'],
        as_dict=True
    )
    return bank_map or {}
