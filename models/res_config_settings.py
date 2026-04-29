from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests
import json


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    finapify_n8n_url = fields.Char(string='Finapify n8n Webhook URL')
    finapify_callback_secret = fields.Char(string='Finapify Callback Secret')
    finapify_api_key = fields.Char(string='Finapify API Key')
    finapify_api_secret = fields.Char(string='Finapify API Secret')
    finapify_api_url = fields.Char(string='Finapify API Base URL', default='https://api.finapify.com')
    finapify_is_authenticated = fields.Boolean(string='API Authenticated', readonly=True)
    finapify_last_auth_at = fields.Datetime(string='Last Authentication', readonly=True)
    finapify_auth_error = fields.Text(string='Authentication Error', readonly=True)

    @api.model
    def get_values(self):
        res = super().get_values()
        icp = self.env['ir.config_parameter'].sudo()
        res.update({
            'finapify_n8n_url': icp.get_param('finapify_payments.n8n_url', default='https://n8n.finapify.com/webhook-test/odoo'),
            'finapify_callback_secret': icp.get_param('finapify_payments.callback_secret', default=''),
            'finapify_api_key': icp.get_param('finapify_payments.api_key', default=''),
            'finapify_api_secret': icp.get_param('finapify_payments.api_secret', default=''),
            'finapify_api_url': icp.get_param('finapify_payments.api_url', default='https://api.finapify.com'),
            'finapify_is_authenticated': icp.get_param('finapify_payments.is_authenticated', default='False') == 'True',
            'finapify_last_auth_at': icp.get_param('finapify_payments.last_auth_at', default=''),
            'finapify_auth_error': icp.get_param('finapify_payments.auth_error', default=''),
        })
        return res

    def set_values(self):
        super().set_values()
        icp = self.env['ir.config_parameter'].sudo()
        if self.finapify_n8n_url:
            icp.set_param('finapify_payments.n8n_url', self.finapify_n8n_url)
        if self.finapify_callback_secret:
            icp.set_param('finapify_payments.callback_secret', self.finapify_callback_secret)
        if self.finapify_api_key:
            icp.set_param('finapify_payments.api_key', self.finapify_api_key)
        if self.finapify_api_secret:
            icp.set_param('finapify_payments.api_secret', self.finapify_api_secret)
        if self.finapify_api_url:
            icp.set_param('finapify_payments.api_url', self.finapify_api_url)

    def test_finapify_authentication(self):
        """Test Finapify API authentication"""
        self.ensure_one()
        icp = self.env['ir.config_parameter'].sudo()

        api_key = self.finapify_api_key
        api_secret = self.finapify_api_secret
        api_url = self.finapify_api_url

        if not api_key or not api_secret:
            raise UserError(_('API Key and Secret are required for authentication.'))

        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }

            # Test with health endpoint
            url = f"{api_url}/health"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                # Authentication successful
                icp.set_param('finapify_payments.is_authenticated', 'True')
                icp.set_param('finapify_payments.last_auth_at', fields.Datetime.now())
                icp.set_param('finapify_payments.auth_error', '')

                # Log successful authentication
                self.env['finapify.log'].sudo().create({
                    'company_id': self.env.company.id,
                    'action': 'api_auth',
                    'level': 'info',
                    'message': 'API authentication successful',
                })

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Authentication Successful'),
                        'message': _('Finapify API authentication successful! API Key: %s') % api_key,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                # Authentication failed
                error_msg = response.text or f'HTTP {response.status_code}'
                icp.set_param('finapify_payments.is_authenticated', 'False')
                icp.set_param('finapify_payments.auth_error', error_msg)

                # Log failed authentication
                self.env['finapify.log'].sudo().create({
                    'company_id': self.env.company.id,
                    'action': 'api_auth',
                    'level': 'error',
                    'message': f'API authentication failed: {error_msg}',
                })

                raise UserError(_('Authentication failed: %s') % error_msg)

        except requests.exceptions.Timeout:
            error_msg = 'Request timeout'
            icp.set_param('finapify_payments.is_authenticated', 'False')
            icp.set_param('finapify_payments.auth_error', error_msg)
            raise UserError(_('Connection timeout: %s') % error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            icp.set_param('finapify_payments.is_authenticated', 'False')
            icp.set_param('finapify_payments.auth_error', error_msg)
            raise UserError(_('Connection error: %s') % error_msg)

        except Exception as e:
            error_msg = str(e)
            icp.set_param('finapify_payments.is_authenticated', 'False')
            icp.set_param('finapify_payments.auth_error', error_msg)
            raise UserError(_('Authentication error: %s') % error_msg)

    def is_finapify_authenticated(self):
        """Check if API is authenticated"""
        icp = self.env['ir.config_parameter'].sudo()
        is_auth = icp.get_param('finapify_payments.is_authenticated', default='False') == 'True'
        return is_auth

    def get_finapify_auth_status(self):
        """Get authentication status details"""
        icp = self.env['ir.config_parameter'].sudo()
        return {
            'is_authenticated': icp.get_param('finapify_payments.is_authenticated', default='False') == 'True',
            'last_auth_at': icp.get_param('finapify_payments.last_auth_at', default=''),
            'auth_error': icp.get_param('finapify_payments.auth_error', default=''),
            'api_key': icp.get_param('finapify_payments.api_key', default=''),
        }
