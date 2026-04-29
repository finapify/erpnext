import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .utils import (
    generate_uuid, sha256_hex, safe_json_dumps, mask_secrets,
    http_post_json, check_finapify_authenticated
)


class FinapifyPaymentRequest(models.Model):
    _name = 'finapify.payment.request'
    _description = 'Finapify Payment Request'
    _order = 'id desc'

    name = fields.Char(required=True, default=lambda self: _('New'))
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    vendor_bill_id = fields.Many2one('account.move', required=True, domain=[('move_type', 'in', ('in_invoice','in_refund'))])
    vendor_id = fields.Many2one('res.partner', related='vendor_bill_id.partner_id', store=True)

    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)

    source_bank_id = fields.Char(required=True)
    vendor_bank_id = fields.Char(required=True)

    otp_required = fields.Boolean(default=True)

    status = fields.Selection([
        ('draft','Draft'),
        ('review','Review'),
        ('otp_pending','OTP Pending'),
        ('submitted','Submitted'),
        ('processing','Processing'),
        ('success','Success'),
        ('failed','Failed'),
        ('cancelled','Cancelled'),
    ], default='draft', index=True)

    idempotency_key = fields.Char(index=True)
    correlation_id = fields.Char(index=True)
    n8n_request_id = fields.Char(index=True)
    finapify_ref = fields.Char(index=True)

    request_payload_json = fields.Text()
    response_payload_json = fields.Text()

    created_payment_ids = fields.Many2many('account.payment', string='Created Payments')

    reconciliation_status = fields.Selection([
        ('not_started','Not started'),
        ('partial','Partial'),
        ('reconciled','Reconciled'),
    ], default='not_started', index=True)

    attempts = fields.Integer(default=0)
    next_retry_at = fields.Datetime()
    last_error = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name') in (False, _('New'), 'New'):
                vals['name'] = seq.next_by_code('finapify.payment.request') or _('New')
        return super().create(vals_list)

    _sql_constraints = [
        ('uniq_company_idem', 'unique(company_id, idempotency_key)', 'Duplicate payment request (idempotency).'),
    ]

    # ----------------------------
    # Logging helper
    # ----------------------------
    def _log(self, action, level='info', message=None, req=None, resp=None):
        for rec in self:
            self.env['finapify.log'].sudo().create({
                'company_id': rec.company_id.id,
                'user_id': self.env.user.id,
                'correlation_id': rec.correlation_id,
                'model': rec._name,
                'record_id': rec.id,
                'action': action,
                'level': level,
                'message': message or '',
                'request_json': safe_json_dumps(mask_secrets(req or {})) if req else False,
                'response_json': safe_json_dumps(resp) if resp else False,
            })

    def _get_connection(self):
        conn = self.env['finapify.connection'].search([
            ('company_id','=', self.company_id.id),
            ('user_id','=', self.env.user.id),
        ], limit=1)
        if not conn or not conn.is_connected:
            raise UserError(_('Finapify is not connected for this user/company. Go to Finapify Connection.'))
        return conn

    def _get_n8n_url(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'finapify_payments.n8n_url',
            default='https://n8n.finapify.com/webhook-test/odoo'
        )

    def _compute_idempotency_key(self):
        self.ensure_one()
        bill = self.vendor_bill_id
        base = f"single|{self.company_id.id}|{bill.id}|{self.amount}|{self.currency_id.name}|{self.source_bank_id}|{self.vendor_bank_id}"
        return sha256_hex(base)

    def action_submit_to_n8n(self, otp_value: str):
        """Submit the payment request to n8n. If n8n returns success, create payment + reconcile.
        If processing, wait for callback.
        """
        self.ensure_one()
        
        # Check if Finapify API is authenticated
        check_finapify_authenticated(self.env)
        
        if self.status not in ('draft','review','otp_pending','failed'):
            raise UserError(_('This request cannot be submitted in current state.'))

        bill = self.vendor_bill_id
        if bill.state != 'posted':
            raise UserError(_('Vendor bill must be posted.'))
        if bill.amount_residual <= 0:
            raise UserError(_('Vendor bill has no residual amount.'))

        conn = self._get_connection()
        jwt = conn.get_supabase_jwt()
        if not jwt:
            raise UserError(_('Supabase JWT missing. Reconnect Finapify.'))

        # journal mapping check early
        jm = self.env['finapify.journal.map'].search([
            ('company_id','=', self.company_id.id),
            ('finapify_source_bank_id','=', self.source_bank_id),
            ('active','=', True)
        ], limit=1)
        if not jm:
            raise UserError(_('Map this Finapify Source Bank ID to an Odoo Bank Journal in Finapify Settings.'))

        correlation_id = self.correlation_id or generate_uuid()
        idem = self.idempotency_key or self._compute_idempotency_key()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        callback_url = f"{base_url}/finapify/callback"

        payload = {
            'product': 'odoo',
            'action': 'initiate_payment',
            'company_id': self.company_id.id,
            'user_id': self.env.user.id,
            'correlation_id': correlation_id,
            'idempotency_key': idem,
            'connection': {
                'consent_id': conn.consent_id,
                'default_source_bank_id': conn.default_source_bank_id or self.source_bank_id,
            },
            'otp': {'required': bool(self.otp_required), 'value': otp_value or ''},
            'payment': {
                'mode': 'single',
                'currency': self.currency_id.name,
                'total_amount': float(self.amount),
                'reference': self.name,
            },
            'items': [
                {
                    'bill_id': bill.id,
                    'bill_name': bill.name,
                    'vendor_id': self.vendor_id.id,
                    'vendor_name': self.vendor_id.name,
                    'amount': float(self.amount),
                    'vendor_bank_id': self.vendor_bank_id,
                    'source_bank_id': self.source_bank_id,
                }
            ],
            'callback': {
                'url': callback_url,
                'signature_type': 'hmac_sha256'
            }
        }

        headers = {"Authorization": f"Bearer {jwt}"}
        n8n_url = self._get_n8n_url()

        self.write({
            'status': 'submitted',
            'correlation_id': correlation_id,
            'idempotency_key': idem,
            'request_payload_json': safe_json_dumps(payload),
            'attempts': self.attempts + 1,
        })
        self._log('initiate', 'info', 'Submitting payment to n8n', req=payload)

        status_code, data = http_post_json(n8n_url, headers=headers, payload=payload, timeout_s=45)

        self.write({
            'response_payload_json': safe_json_dumps(data),
            'n8n_request_id': data.get('n8n_request_id') or self.n8n_request_id,
        })

        if status_code >= 400 or not data.get('ok', True):
            self.write({'status': 'failed', 'last_error': safe_json_dumps(data)})
            self._log('initiate', 'error', 'n8n returned error', resp=data)
            return

        st = data.get('status')
        self._log('initiate', 'info', f"n8n status: {st}", resp=data)

        if st == 'success':
            self._apply_results_and_finalize(data)
        elif st in ('processing', 'part_success'):
            self.write({'status': 'processing'})
        else:
            # treat unknown status as failed
            self.write({'status': 'failed', 'last_error': safe_json_dumps(data)})

    def _apply_results_and_finalize(self, data: dict):
        """Create payments and reconcile based on results array."""
        self.ensure_one()
        results = data.get('results') or []
        if not results:
            # allow single success without result array
            self.write({'status': 'success'})
            return

        # find matching result by bill_id
        bill_id = self.vendor_bill_id.id
        match = None
        for r in results:
            if int(r.get('bill_id') or 0) == bill_id:
                match = r
                break
        if not match:
            self.write({'status': 'processing'})
            return

        if match.get('status') != 'success':
            self.write({'status': 'failed', 'last_error': match.get('message') or 'Payment failed'})
            return

        fin_ref = match.get('finapify_ref')
        paid_amount = float(match.get('paid_amount') or self.amount)
        self.write({'finapify_ref': fin_ref, 'status': 'success'})

        # idempotency at payment creation level
        if fin_ref:
            existing_txn = self.env['finapify.txn'].search([
                ('company_id','=', self.company_id.id),
                ('finapify_ref','=', fin_ref)
            ], limit=1)
            if existing_txn and existing_txn.payment_ids:
                self.write({'created_payment_ids': [(6, 0, existing_txn.payment_ids.ids)]})
                self._attempt_reconcile()
                return

        payments = self._create_payments_for_success(paid_amount, fin_ref)
        if fin_ref:
            self.env['finapify.txn'].sudo().create({
                'company_id': self.company_id.id,
                'finapify_ref': fin_ref,
                'request_model': self._name,
                'request_id': self.id,
                'payment_ids': [(6, 0, payments.ids)],
            })

        self.write({'created_payment_ids': [(6, 0, payments.ids)]})
        self._attempt_reconcile()

    def _create_payments_for_success(self, paid_amount: float, finapify_ref: str):
        self.ensure_one()
        jm = self.env['finapify.journal.map'].search([
            ('company_id','=', self.company_id.id),
            ('finapify_source_bank_id','=', self.source_bank_id),
            ('active','=', True)
        ], limit=1)
        if not jm:
            raise UserError(_('Missing journal mapping for source bank ID.'))

        journal = jm.journal_id
        vendor = self.vendor_id

        # select a payment method line
        pml = journal.outbound_payment_method_line_ids[:1]
        if not pml:
            raise UserError(_('No outbound payment method line found on the selected journal.'))

        ref = f"Finapify {finapify_ref or ''} {self.vendor_bill_id.name}".strip()

        payment = self.env['account.payment'].create({
            'company_id': self.company_id.id,
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': vendor.id,
            'amount': paid_amount,
            'currency_id': self.currency_id.id,
            'journal_id': journal.id,
            'payment_method_line_id': pml.id,
            'ref': ref,
        })
        payment.action_post()
        self._log('create_payment', 'info', f"Created payment {payment.name}")
        return payment

    def _attempt_reconcile(self):
        self.ensure_one()
        bill = self.vendor_bill_id
        if not self.created_payment_ids:
            self.write({'reconciliation_status': 'not_started'})
            return

        try:
            # reconcile payable lines
            bill_lines = bill.line_ids.filtered(lambda l: l.account_id.account_type == 'liability_payable' and not l.reconciled)
            pay_lines = self.created_payment_ids.line_ids.filtered(lambda l: l.account_id.account_type == 'liability_payable' and not l.reconciled)

            lines = (bill_lines | pay_lines)
            if lines:
                lines.reconcile()

            # check residual
            if bill.amount_residual == 0:
                self.write({'reconciliation_status': 'reconciled'})
            else:
                self.write({'reconciliation_status': 'partial'})
            self._log('reconcile', 'info', f"Reconciliation status: {self.reconciliation_status}")
        except Exception as e:
            self.write({'reconciliation_status': 'partial', 'last_error': str(e)})
            self._log('reconcile', 'error', f"Reconcile failed: {e}")

    def action_retry(self):
        self.ensure_one()
        if self.status not in ('failed','processing'):
            raise UserError(_('Only failed or processing requests can be retried.'))
        self.env['finapify.job'].sudo().enqueue_retry(self._name, self.id)
        self._log('retry', 'info', 'Enqueued retry job')

    def action_retry_reconcile(self):
        self.ensure_one()
        self.env['finapify.job'].sudo().enqueue_reconcile(self._name, self.id)
        self._log('reconcile', 'info', 'Enqueued reconcile job')
