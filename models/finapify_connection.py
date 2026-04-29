import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .utils import encrypt_text, decrypt_text, generate_uuid, safe_json_dumps, mask_secrets


class FinapifyConnection(models.Model):
    _name = 'finapify.connection'
    _description = 'Finapify Connection'
    _rec_name = 'name'

    name = fields.Char(default='Finapify Connection', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user)

    supabase_user_id = fields.Char()
    consent_id = fields.Char()

    supabase_jwt_encrypted = fields.Text(string='Supabase JWT (Encrypted)', groups='base.group_system')
    is_connected = fields.Boolean(default=False)
    state = fields.Selection([
        ('disconnected', 'Disconnected'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], default='disconnected')

    default_source_bank_id = fields.Char(string='Default Payer Bank ID')
    bank_accounts_json = fields.Text(string='Linked Bank Accounts (JSON)')

    last_sync_at = fields.Datetime()
    error_message = fields.Text()

    _sql_constraints = [
        ('uniq_company_user', 'unique(company_id, user_id)', 'Only one connection per user and company is allowed.'),
    ]

    # -----------------------
    # Settings helpers
    # -----------------------
    def _get_callback_secret(self):
        secret = self.env['ir.config_parameter'].sudo().get_param('finapify_payments.callback_secret')
        if not secret:
            # create a default secret if missing
            secret = generate_uuid().replace('-', '')
            self.env['ir.config_parameter'].sudo().set_param('finapify_payments.callback_secret', secret)
        return secret

    def set_supabase_jwt(self, jwt_plain: str):
        self.ensure_one()
        secret = self._get_callback_secret()
        self.supabase_jwt_encrypted = encrypt_text(jwt_plain or '', secret)

    def get_supabase_jwt(self) -> str:
        self.ensure_one()
        secret = self._get_callback_secret()
        return decrypt_text(self.supabase_jwt_encrypted or '', secret)

    def action_disconnect(self):
        for rec in self:
            rec.write({
                'supabase_user_id': False,
                'consent_id': False,
                'supabase_jwt_encrypted': False,
                'default_source_bank_id': False,
                'bank_accounts_json': False,
                'is_connected': False,
                'state': 'disconnected',
                'error_message': False,
            })

    def action_refresh_accounts(self):
        """Optional: call n8n to refresh linked accounts.

        This is implemented as a generic 'fetch_accounts' action.
        n8n flow should accept it and return bank_accounts.
        """
        self.ensure_one()
        if not self.is_connected:
            raise UserError(_('Connect Finapify first.'))

        n8n_url = self.env['ir.config_parameter'].sudo().get_param(
            'finapify_payments.n8n_url',
            default='https://n8n.finapify.com/webhook-test/odoo'
        )

        jwt = self.get_supabase_jwt()
        if not jwt:
            raise UserError(_('Supabase JWT missing. Reconnect Finapify.'))

        payload = {
            'product': 'odoo',
            'action': 'fetch_accounts',
            'company_id': self.company_id.id,
            'user_id': self.user_id.id,
        }
        headers = {"Authorization": f"Bearer {jwt}"}

        from .utils import http_post_json
        status, data = http_post_json(n8n_url, headers=headers, payload=payload, timeout_s=30)

        if status >= 400 or not data.get('ok', True):
            self.write({'state': 'error', 'error_message': safe_json_dumps(data)})
            raise UserError(_('Failed to refresh accounts.'))

        accounts = data.get('bank_accounts') or data.get('accounts') or []
        self.write({
            'bank_accounts_json': safe_json_dumps(accounts),
            'last_sync_at': fields.Datetime.now(),
            'state': 'connected',
            'error_message': False,
        })
        return True
