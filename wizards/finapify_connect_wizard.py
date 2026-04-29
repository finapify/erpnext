from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FinapifyConnectWizard(models.TransientModel):
    _name = 'finapify.connect.wizard'
    _description = 'Connect Finapify Wizard'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    supabase_jwt = fields.Text(string='Supabase JWT', required=True)
    consent_id = fields.Char(string='Consent ID', required=True)
    default_source_bank_id = fields.Char(string='Default Payer Bank ID', required=True)

    bank_accounts_json = fields.Text(string='Linked Bank Accounts JSON', help='Optional: paste linked accounts JSON for reference.')

    def action_connect(self):
        self.ensure_one()
        conn = self.env['finapify.connection'].search([
            ('company_id','=', self.company_id.id),
            ('user_id','=', self.env.user.id),
        ], limit=1)
        if not conn:
            conn = self.env['finapify.connection'].create({
                'company_id': self.company_id.id,
                'user_id': self.env.user.id,
                'name': 'Finapify Connection',
            })

        conn.set_supabase_jwt(self.supabase_jwt)
        conn.write({
            'consent_id': self.consent_id,
            'default_source_bank_id': self.default_source_bank_id,
            'bank_accounts_json': self.bank_accounts_json,
            'is_connected': True,
            'state': 'connected',
            'error_message': False,
        })
        return {'type': 'ir.actions.act_window_close'}
