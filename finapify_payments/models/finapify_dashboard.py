import frappe
from frappe import _
from frappe.model.document import Document


class FinapifyDashboard(Document):

    def get_dashboard_data(self):
        return {
            'quick_links': [
                {
                    'name': 'Finapify Connection',
                    'icon': 'fa fa-link',
                    'doctype': 'Finapify Connection',
                    'description': _('Manage Finapify API connections and authentication'),
                },
                {
                    'name': 'Payment Requests',
                    'icon': 'fa fa-paper-plane',
                    'doctype': 'Finapify Payment Request',
                    'description': _('Create and manage individual payment requests'),
                },
                {
                    'name': 'Payment Batches',
                    'icon': 'fa fa-credit-card',
                    'doctype': 'Finapify Payment Batch',
                    'description': _('Manage bulk payment batches'),
                },
                {
                    'name': 'Vendor Bank Mapping',
                    'icon': 'fa fa-building',
                    'doctype': 'Finapify Vendor Bank Map',
                    'description': _('Map vendors to their bank accounts'),
                },
                {
                    'name': 'Journal Mapping',
                    'icon': 'fa fa-book',
                    'doctype': 'Finapify Journal Map',
                    'description': _('Configure journal mapping from Finapify banks'),
                },
                {
                    'name': 'Logs & Audit',
                    'icon': 'fa fa-history',
                    'doctype': 'Finapify Log',
                    'description': _('View system logs and audit trail'),
                },
            ],
            'stats': {
                'total_connections': frappe.db.count('Finapify Connection'),
                'pending_requests': frappe.db.count('Finapify Payment Request', {'status': 'Draft'}),
                'completed_batches': frappe.db.count('Finapify Payment Batch', {'status': 'Success'}),
            },
        }

    def get_authentication_status(self):
        return {
            'is_authenticated': frappe.db.get_single_value('Finapify Settings', 'is_authenticated') or False,
            'has_api_key': bool(frappe.db.get_single_value('Finapify Settings', 'api_key')),
            'api_url': frappe.db.get_single_value('Finapify Settings', 'api_url') or 'https://api.finapify.com/webhook/erpnext',
            'last_auth_at': frappe.db.get_single_value('Finapify Settings', 'last_auth_at') or '',
            'auth_error': frappe.db.get_single_value('Finapify Settings', 'auth_error') or '',
        }
