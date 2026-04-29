from odoo import api, fields, models, _


class FinapifyDashboard(models.Model):
    _name = 'finapify.dashboard'
    _description = 'Finapify Dashboard'

    name = fields.Char(default='Finapify Dashboard')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    def get_dashboard_data(self):
        """Get dashboard data with quick access links"""
        return {
            'quick_links': [
                {
                    'name': 'Finapify Connection',
                    'icon': 'fa fa-link',
                    'action': 'action_finapify_connection',
                    'description': 'Manage Finapify API connections and authentication',
                },
                {
                    'name': 'Payment Requests',
                    'icon': 'fa fa-paper-plane',
                    'action': 'action_finapify_payment_request',
                    'description': 'Create and manage individual payment requests',
                },
                {
                    'name': 'Payment Batches',
                    'icon': 'fa fa-credit-card',
                    'action': 'action_finapify_payment_batch',
                    'description': 'Manage bulk payment batches',
                },
                {
                    'name': 'Vendor Bank Mapping',
                    'icon': 'fa fa-building',
                    'action': 'action_finapify_vendor_bank_map',
                    'description': 'Map vendors to their bank accounts',
                },
                {
                    'name': 'Journal Mapping',
                    'icon': 'fa fa-book',
                    'action': 'action_finapify_journal_map',
                    'description': 'Configure journal mapping from Finapify banks',
                },
                {
                    'name': 'Reconciliation Center',
                    'icon': 'fa fa-balance-scale',
                    'action': 'action_finapify_reconciliation',
                    'description': 'Reconcile payments with invoices',
                },
                {
                    'name': 'Logs & Audit',
                    'icon': 'fa fa-history',
                    'action': 'action_finapify_log',
                    'description': 'View system logs and audit trail',
                },
            ],
            'stats': {
                'total_connections': self.env['finapify.connection'].search_count([]),
                'pending_requests': self.env['finapify.payment.request'].search_count(
                    [('state', '=', 'pending')]
                ),
                'completed_batches': self.env['finapify.payment.batch'].search_count(
                    [('state', '=', 'completed')]
                ),
            }
        }

    def get_authentication_status(self):
        """Get current Finapify API authentication status"""
        icp = self.env['ir.config_parameter'].sudo()
        return {
            'is_authenticated': icp.get_param('finapify_payments.is_authenticated', default='False') == 'True',
            'api_key': icp.get_param('finapify_payments.api_key', default=''),
            'api_url': icp.get_param('finapify_payments.api_url', default='https://api.finapify.com'),
            'last_auth_at': icp.get_param('finapify_payments.last_auth_at', default=''),
            'auth_error': icp.get_param('finapify_payments.auth_error', default=''),
        }
