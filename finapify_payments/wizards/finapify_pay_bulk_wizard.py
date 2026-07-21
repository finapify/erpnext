import frappe
from frappe import _
from frappe.model.document import Document


class FinapifyPayBulkWizard(Document):

    def before_insert(self):
        active_ids = frappe.flags.get('active_ids') or []
        if active_ids and not self.bill_ids:
            bills = frappe.get_list(
                'Purchase Invoice',
                filters={'name': ['in', active_ids], 'docstatus': 1},
                fields=['name', 'company', 'currency', 'outstanding_amount'],
            )
            if bills:
                self.company = bills[0].company
                for b in bills:
                    self.append('bill_ids', {'vendor_bill': b.name})

                conn_name = frappe.db.get_value(
                    'Finapify Connection',
                    {'company': bills[0].company, 'user': frappe.session.user},
                    'name'
                )
                if conn_name:
                    conn = frappe.get_doc('Finapify Connection', conn_name)
                    if conn.default_source_bank_id:
                        self.source_bank_id = conn.default_source_bank_id

    @frappe.whitelist()
    def action_pay_bulk(self):
        bill_names = [row.vendor_bill for row in self.bill_ids]
        if not bill_names:
            frappe.throw(_('Select at least one vendor bill.'))

        bills = [frappe.get_doc('Purchase Invoice', n) for n in bill_names]

        companies = {b.company for b in bills}
        if len(companies) > 1:
            frappe.throw(_('All selected bills must belong to the same company.'))

        for b in bills:
            if b.docstatus != 1:
                frappe.throw(_('Bill %s must be submitted.') % b.name)
            if not b.outstanding_amount or b.outstanding_amount <= 0:
                frappe.throw(_('Bill %s has no outstanding amount.') % b.name)

        company = bills[0].company

        batch = frappe.get_doc({
            'doctype': 'Finapify Payment Batch',
            'company': company,
            'mode': self.mode or 'one_bank',
            'source_bank_id': self.source_bank_id,
            'currency': bills[0].currency,
            'otp_required': 1,
            'status': 'OTP Pending',
        })

        for b in bills:
            vendor_bank_id = frappe.db.get_value(
                'Finapify Vendor Bank Map',
                {'company': b.company, 'supplier': b.supplier},
                'finapify_vendor_bank_id'
            )
            if not vendor_bank_id:
                frappe.throw(_('Missing Finapify Vendor Bank ID for vendor: %s') % b.supplier)

            if not self.source_bank_id:
                frappe.throw(_('Select a payer bank ID.'))

            batch.append('line_ids', {
                'vendor_bill': b.name,
                'vendor': b.supplier,
                'amount': b.outstanding_amount,
                'currency': b.currency,
                'vendor_bank_id': vendor_bank_id,
                'source_bank_id': self.source_bank_id,
                'status': 'Pending',
            })

        batch.insert(ignore_permissions=True)
        batch.action_submit_to_n8n(self.get_password('otp', raise_exception=False))

        return {
            'doctype': 'Finapify Payment Batch',
            'name': batch.name,
        }
