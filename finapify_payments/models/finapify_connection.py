import frappe
from frappe import _
from frappe.model.document import Document

from .utils import (
    encrypt_text, decrypt_text, generate_uuid, safe_json_dumps, http_post_json,
    get_finapify_secret,
)


class FinapifyConnection(Document):

    def _get_callback_secret(self):
        secret = get_finapify_secret('callback_secret')
        if not secret:
            secret = generate_uuid().replace('-', '')
            frappe.db.set_value('Finapify Settings', 'Finapify Settings', 'callback_secret', secret)
        return secret

    def set_supabase_jwt(self, jwt_plain: str):
        secret = self._get_callback_secret()
        self.db_set('supabase_jwt_encrypted', encrypt_text(jwt_plain or '', secret))

    def get_supabase_jwt(self) -> str:
        secret = self._get_callback_secret()
        return decrypt_text(self.supabase_jwt_encrypted or '', secret)

    @frappe.whitelist()
    def action_disconnect(self):
        self.db_set('supabase_user_id', '')
        self.db_set('consent_id', '')
        self.db_set('supabase_jwt_encrypted', '')
        self.db_set('default_source_bank_id', '')
        self.db_set('bank_accounts_json', '')
        self.db_set('is_connected', 0)
        self.db_set('state', 'Disconnected')
        self.db_set('error_message', '')

    @frappe.whitelist()
    def action_refresh_accounts(self):
        if not self.is_connected:
            frappe.throw(_('Connect Finapify first.'))

        n8n_url = (
            frappe.db.get_single_value('Finapify Settings', 'n8n_url')
            or 'https://n8n.finapify.com/webhook-test/erpnext'
        )

        jwt = self.get_supabase_jwt()
        if not jwt:
            frappe.throw(_('Supabase JWT missing. Reconnect Finapify.'))

        payload = {
            'product': 'frappe',
            'action': 'fetch_accounts',
            'company': self.company,
            'user': frappe.session.user,
        }
        headers = {'Authorization': f'Bearer {jwt}'}

        status, data = http_post_json(n8n_url, headers=headers, payload=payload, timeout_s=30)

        if status >= 400 or not data.get('ok', True):
            self.db_set('state', 'Error')
            self.db_set('error_message', safe_json_dumps(data))
            frappe.throw(_('Failed to refresh accounts.'))

        accounts = data.get('bank_accounts') or data.get('accounts') or []
        self.db_set('bank_accounts_json', safe_json_dumps(accounts))
        self.db_set('last_sync_at', frappe.utils.now())
        self.db_set('state', 'Connected')
        self.db_set('error_message', '')
        return True
