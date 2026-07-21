import frappe
from frappe import _
from frappe.model.document import Document


class FinapifySettings(Document):
    """Single DocType controller for Finapify Settings."""

    def validate(self):
        if not self.api_url:
            self.api_url = 'https://api.finapify.com/webhook/erpnext'

    @frappe.whitelist()
    def test_finapify_authentication(self):
        import requests

        api_key = self.get_password('api_key', raise_exception=False)
        api_secret = self.get_password('api_secret', raise_exception=False)
        api_url = self.api_url or 'https://api.finapify.com/webhook/erpnext'

        if not api_key or not api_secret:
            frappe.throw(_('API Key and Secret are required for authentication.'))

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }
            response = requests.get(f'{api_url}/health', headers=headers, timeout=10)

            if response.status_code == 200:
                self.db_set('is_authenticated', 1)
                self.db_set('last_auth_at', frappe.utils.now())
                self.db_set('auth_error', '')

                frappe.get_doc({
                    'doctype': 'Finapify Log',
                    'action': 'api_auth',
                    'level': 'info',
                    'message': 'API authentication successful',
                }).insert(ignore_permissions=True)

                frappe.msgprint(_('Finapify API authentication successful!'), alert=True, indicator='green')
            else:
                error_msg = response.text or f'HTTP {response.status_code}'
                self.db_set('is_authenticated', 0)
                self.db_set('auth_error', error_msg)
                frappe.throw(_('Authentication failed: %s') % error_msg)

        except requests.exceptions.Timeout:
            self.db_set('is_authenticated', 0)
            self.db_set('auth_error', 'Request timeout')
            frappe.throw(_('Connection timeout while authenticating.'))

        except requests.exceptions.RequestException as e:
            self.db_set('is_authenticated', 0)
            self.db_set('auth_error', str(e))
            frappe.throw(_('Connection error: %s') % str(e))

    def is_finapify_authenticated(self):
        return bool(self.is_authenticated)

    def get_finapify_auth_status(self):
        return {
            'is_authenticated': bool(self.is_authenticated),
            'last_auth_at': self.last_auth_at or '',
            'auth_error': self.auth_error or '',
            'has_api_key': bool(self.get_password('api_key', raise_exception=False)),
        }
