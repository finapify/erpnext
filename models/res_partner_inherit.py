import frappe
from frappe import _
from frappe.model.document import Document


class FinapifySupplier(Document):
    """Extends Supplier with Finapify vendor bank map helper."""

    def get_finapify_bank_map(self):
        return frappe.db.get_value(
            'Finapify Vendor Bank Map',
            {'supplier': self.name},
            ['finapify_vendor_bank_id', 'verified'],
            as_dict=True
        ) or {}


@frappe.whitelist()
def get_vendor_bank_mappings(supplier):
    """Return Finapify bank mapping for a supplier."""
    if not supplier:
        return {}
    return frappe.db.get_value(
        'Finapify Vendor Bank Map',
        {'supplier': supplier},
        ['finapify_vendor_bank_id', 'verified'],
        as_dict=True
    ) or {}
