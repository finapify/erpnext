import frappe
from frappe import _
from frappe.model.document import Document


class FinapifyPaySingleWizard(Document):

    def before_insert(self):
        active_id = frappe.flags.get('active_id') or frappe.form_dict.get('vendor_bill')
        if active_id and not self.vendor_bill:
            bill = frappe.get_doc('Purchase Invoice', active_id)
            self.vendor_bill = bill.name
            self.amount = bill.outstanding_amount
            self.currency = bill.currency

            conn_name = frappe.db.get_value(
                'Finapify Connection',
                {'company': bill.company, 'user': frappe.session.user},
                'name'
            )
            if conn_name:
                conn = frappe.get_doc('Finapify Connection', conn_name)
                if conn.default_source_bank_id:
                    self.source_bank_id = conn.default_source_bank_id

            vendor_map = frappe.db.get_value(
                'Finapify Vendor Bank Map',
                {'company': bill.company, 'supplier': bill.supplier},
                'finapify_vendor_bank_id'
            )
            if vendor_map:
                self.vendor_bank_id = vendor_map

    @frappe.whitelist()
    def action_pay(self):
        if not self.vendor_bill:
            frappe.throw(_('Vendor bill is required.'))

        bill = frappe.get_doc('Purchase Invoice', self.vendor_bill)

        if bill.docstatus != 1:
            frappe.throw(_('Bill must be submitted before payment.'))
        if not self.amount or self.amount <= 0:
            frappe.throw(_('Amount must be positive.'))

        req = frappe.get_doc({
            'doctype': 'Finapify Payment Request',
            'company': bill.company,
            'vendor_bill': bill.name,
            'vendor': bill.supplier,
            'amount': self.amount,
            'currency': bill.currency,
            'source_bank_id': self.source_bank_id,
            'vendor_bank_id': self.vendor_bank_id,
            'otp_required': 1,
            'status': 'OTP Pending',
        })
        req.insert(ignore_permissions=True)
        req.action_submit_to_n8n(self.get_password('otp', raise_exception=False))

        return {
            'doctype': 'Finapify Payment Request',
            'name': req.name,
        }
