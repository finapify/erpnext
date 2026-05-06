import frappe
from frappe import _
from frappe.model.document import Document


class FinapifyVendorBankMap(Document):

    def validate(self):
        if self.finapify_vendor_bank_id and len(self.finapify_vendor_bank_id.strip()) < 3:
            frappe.throw(_('Finapify Vendor Bank ID looks too short.'))
