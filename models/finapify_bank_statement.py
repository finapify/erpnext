from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import requests
import json


class FinapifyBankStatement(models.Model):
    _name = 'finapify.bank.statement'
    _description = 'Finapify Bank Statement'
    _order = 'date_from desc'

    name = fields.Char(required=True, readonly=True, states={'draft': [('readonly', False)]})
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, readonly=True, states={'draft': [('readonly', False)]})
    
    # Bank & Date Selection
    bank_id = fields.Selection(selection='_get_bank_selection', string='Bank Account', required=True, readonly=True, states={'draft': [('readonly', False)]})
    bank_name = fields.Char(string='Bank Name', compute='_compute_bank_name', store=True)
    date_from = fields.Date(required=True, readonly=True, states={'draft': [('readonly', False)]})
    date_to = fields.Date(required=True, readonly=True, states={'draft': [('readonly', False)]})
    
    # Statement Details
    state = fields.Selection([
        ('draft', 'Draft'),
        ('fetching', 'Fetching'),
        ('loaded', 'Loaded'),
        ('failed', 'Failed'),
    ], default='draft', readonly=True, index=True)
    
    line_ids = fields.One2many('finapify.bank.statement.line', 'statement_id', string='Transactions', readonly=True, states={'draft': [('readonly', False)]})
    
    # Statistics
    total_transactions = fields.Integer(compute='_compute_stats', store=False)
    total_debit = fields.Monetary(compute='_compute_stats', store=False)
    total_credit = fields.Monetary(compute='_compute_stats', store=False)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    # Metadata
    created_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    fetched_at = fields.Datetime(readonly=True)
    error_message = fields.Text(readonly=True)
    response_json = fields.Text(string='API Response (JSON)', readonly=True)

    def _get_bank_selection(self):
        """Get bank selection from Finapify connection"""
        conn = self.env['finapify.connection'].search([
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        if not conn or not conn.bank_accounts_json:
            return []
        try:
            accounts = json.loads(conn.bank_accounts_json)
            # Ensure each tuple is (value, label)
            return [(acc.get('bank_id'), f"{acc.get('bank_name', 'Unknown')} ({acc.get('account_number', '')})") for acc in accounts]
        except Exception:
            return []

    @api.depends('bank_id')
    def _compute_bank_name(self):
        """Get bank name from Finapify connection"""
        for record in self:
            if not record.bank_id:
                record.bank_name = False
                continue
            
            # Try to get bank name from selection
            selection = dict(self._get_bank_selection())
            record.bank_name = selection.get(record.bank_id, record.bank_id)

    def _compute_stats(self):
        """Compute statement statistics"""
        for record in self:
            record.total_transactions = len(record.line_ids)
            record.total_debit = sum(record.line_ids.filtered(lambda l: l.transaction_type == 'debit').mapped('amount'))
            record.total_credit = sum(record.line_ids.filtered(lambda l: l.transaction_type == 'credit').mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if 'name' not in vals or vals.get('name') in (False, _('New')):
                vals['name'] = seq.next_by_code('finapify.bank.statement') or _('New')
        return super().create(vals_list)

    def fetch_bank_statement(self):
        """Fetch bank statement from Finapify API"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_('Statement must be in draft state to fetch.'))
        
        if not self.bank_id or not self.date_from or not self.date_to:
            raise UserError(_('Bank ID, From Date, and To Date are required.'))
        
        if self.date_from > self.date_to:
            raise UserError(_('From Date cannot be after To Date.'))
        
        # Check authentication
        from .utils import check_finapify_authenticated
        check_finapify_authenticated(self.env)
        
        # Get connection and API details
        conn = self.env['finapify.connection'].search([
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not conn or not conn.is_connected:
            raise UserError(_('Finapify connection is not active. Please reconnect.'))
        
        jwt = conn.get_supabase_jwt()
        if not jwt:
            raise UserError(_('Supabase JWT missing. Reconnect Finapify.'))
        
        try:
            self.write({'state': 'fetching'})
            
            icp = self.env['ir.config_parameter'].sudo()
            api_url = icp.get_param('finapify_payments.api_url', default='https://api.finapify.com')
            
            headers = {
                'Authorization': f'Bearer {jwt}',
                'Content-Type': 'application/json',
            }
            
            payload = {
                'bank_id': self.bank_id,
                'date_from': self.date_from.isoformat(),
                'date_to': self.date_to.isoformat(),
                'consent_id': conn.consent_id,
            }
            
            # Call API to fetch bank statement
            url = f"{api_url}/bank-statements"
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            response_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
            
            self.write({'response_json': json.dumps(response_data, indent=2)})
            
            if response.status_code == 200:
                transactions = response_data.get('transactions', [])
                
                # Clear existing lines and create new ones
                self.line_ids.unlink()
                
                for txn in transactions:
                    self.env['finapify.bank.statement.line'].create({
                        'statement_id': self.id,
                        'transaction_date': txn.get('date'),
                        'description': txn.get('description', ''),
                        'reference': txn.get('reference', ''),
                        'transaction_type': 'debit' if float(txn.get('amount', 0)) < 0 else 'credit',
                        'amount': abs(float(txn.get('amount', 0))),
                        'balance': float(txn.get('balance', 0)),
                        'counterparty_name': txn.get('counterparty_name', ''),
                        'counterparty_account': txn.get('counterparty_account', ''),
                        'raw_json': json.dumps(txn),
                    })
                
                self.write({
                    'state': 'loaded',
                    'fetched_at': fields.Datetime.now(),
                    'error_message': '',
                })
                
                # Log success
                self.env['finapify.log'].sudo().create({
                    'company_id': self.company_id.id,
                    'action': 'bank_statement_fetch',
                    'level': 'info',
                    'message': f'Bank statement fetched successfully for {self.bank_id}: {len(transactions)} transactions',
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Bank statement fetched successfully with %d transactions.') % len(transactions),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                error_msg = response_data.get('error', f'HTTP {response.status_code}')
                self.write({
                    'state': 'failed',
                    'error_message': error_msg,
                })
                
                # Log failure
                self.env['finapify.log'].sudo().create({
                    'company_id': self.company_id.id,
                    'action': 'bank_statement_fetch',
                    'level': 'error',
                    'message': f'Bank statement fetch failed: {error_msg}',
                })
                
                raise UserError(_('API Error: %s') % error_msg)
        
        except requests.exceptions.Timeout:
            self.write({
                'state': 'failed',
                'error_message': 'Request timeout',
            })
            raise UserError(_('Request timeout while fetching bank statement.'))
        
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            self.write({
                'state': 'failed',
                'error_message': error_msg,
            })
            raise UserError(_('Connection error: %s') % error_msg)
        
        except Exception as e:
            error_msg = str(e)
            self.write({
                'state': 'failed',
                'error_message': error_msg,
            })
            raise UserError(_('Error: %s') % error_msg)

    def action_reload_statement(self):
        """Reload the statement data"""
        self.ensure_one()
        self.write({'state': 'draft'})
        return self.fetch_bank_statement()

    def action_set_draft(self):
        """Set statement back to draft"""
        self.ensure_one()
        self.write({'state': 'draft'})

    def get_available_banks(self):
        """Get list of available banks from connection"""
        conn = self.env['finapify.connection'].search([
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not conn or not conn.bank_accounts_json:
            return []
        
        try:
            accounts = json.loads(conn.bank_accounts_json)
            banks = []
            for acc in accounts:
                banks.append({
                    'id': acc.get('bank_id'),
                    'name': f"{acc.get('bank_name', 'Unknown')} ({acc.get('account_number', '')})",
                })
            return banks
        except:
            return []


class FinapifyBankStatementLine(models.Model):
    _name = 'finapify.bank.statement.line'
    _description = 'Finapify Bank Statement Line'
    _order = 'transaction_date desc'

    statement_id = fields.Many2one('finapify.bank.statement', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='statement_id.company_id', store=True, readonly=True)
    
    # Transaction Details
    transaction_date = fields.Date(required=True)
    description = fields.Char(required=True)
    reference = fields.Char()
    transaction_type = fields.Selection([
        ('debit', 'Debit'),
        ('credit', 'Credit'),
    ], required=True)
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one('res.currency', related='statement_id.currency_id', store=True, readonly=True)
    balance = fields.Monetary()
    
    # Counterparty Information
    counterparty_name = fields.Char()
    counterparty_account = fields.Char()
    
    # Reconciliation
    matched_payment_id = fields.Many2one('account.payment')
    reconciliation_status = fields.Selection([
        ('unmatched', 'Unmatched'),
        ('matched', 'Matched'),
        ('reconciled', 'Reconciled'),
    ], default='unmatched')
    
    # Raw Data
    raw_json = fields.Text(readonly=True)
    created_at = fields.Datetime(default=fields.Datetime.now, readonly=True)

    def action_match_payment(self):
        """Open dialog to match this transaction with a payment"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Match Payment'),
            'res_model': 'account.payment',
            'view_mode': 'tree,form',
            'target': 'new',
            'domain': [
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'draft'),
                ('amount', '=', self.amount),
            ],
        }

    def reconcile_with_payment(self, payment_id):
        """Reconcile statement line with payment"""
        self.ensure_one()
        if payment_id:
            self.write({
                'matched_payment_id': payment_id,
                'reconciliation_status': 'reconciled',
            })
