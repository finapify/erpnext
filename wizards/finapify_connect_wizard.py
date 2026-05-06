import frappe
from frappe import _
from frappe.model.document import Document


class FinapifyConnectWizard(Document):

    def action_connect(self):
        name = frappe.db.get_value(
            'Finapify Connection',
            {'company': self.company, 'user': frappe.session.user},
            'name'
        )
        if not name:
            conn = frappe.new_doc('Finapify Connection')
            conn.company = self.company
            conn.user = frappe.session.user
            conn.title = f'Finapify – {self.company}'
            conn.insert(ignore_permissions=True)
        else:
            conn = frappe.get_doc('Finapify Connection', name)

        conn.set_supabase_jwt(self.supabase_jwt)
        conn.db_set('consent_id', self.consent_id)
        conn.db_set('default_source_bank_id', self.default_source_bank_id)
        if self.bank_accounts_json:
            conn.db_set('bank_accounts_json', self.bank_accounts_json)
        conn.db_set('is_connected', 1)
        conn.db_set('state', 'Connected')
        conn.db_set('error_message', '')

        frappe.msgprint(_('Finapify connected successfully!'), alert=True, indicator='green')
        return {'message': 'connected'}
