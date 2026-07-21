import frappe
from frappe import _
from frappe.model.document import Document


class FinapifyJournalMap(Document):

    def validate(self):
        if self.finapify_source_bank_id and len(self.finapify_source_bank_id.strip()) < 3:
            frappe.throw(_('Finapify Source Bank ID looks too short.'))
