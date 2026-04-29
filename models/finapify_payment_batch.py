from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .utils import generate_uuid, sha256_hex, safe_json_dumps, http_post_json, check_finapify_authenticated


class FinapifyPaymentBatch(models.Model):
    _name = 'finapify.payment.batch'
    _description = 'Finapify Payment Batch'
    _order = 'id desc'

    name = fields.Char(required=True, default=lambda self: _('New'))
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    mode = fields.Selection([('one_bank','One bank'),('multi_bank','Multi bank')], default='one_bank', required=True)
    source_bank_id = fields.Char(string='Default Source Bank ID')

    bill_ids = fields.Many2many('account.move', string='Vendor Bills')
    line_ids = fields.One2many('finapify.payment.batch.line', 'batch_id', string='Lines')

    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)
    total_amount = fields.Monetary(compute='_compute_total', store=True)

    otp_required = fields.Boolean(default=True)

    status = fields.Selection([
        ('draft','Draft'),
        ('review','Review'),
        ('otp_pending','OTP Pending'),
        ('submitted','Submitted'),
        ('processing','Processing'),
        ('part_success','Partially Successful'),
        ('success','Success'),
        ('failed','Failed'),
    ], default='draft', index=True)

    idempotency_key = fields.Char(index=True)
    correlation_id = fields.Char(index=True)
    n8n_request_id = fields.Char(index=True)

    request_payload_json = fields.Text()
    response_payload_json = fields.Text()

    reconciliation_status = fields.Selection([
        ('not_started','Not started'),
        ('partial','Partial'),
        ('reconciled','Reconciled'),
    ], default='not_started', index=True)

    attempts = fields.Integer(default=0)
    next_retry_at = fields.Datetime()
    last_error = fields.Text()

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name') in (False, _('New'), 'New'):
                vals['name'] = seq.next_by_code('finapify.payment.batch') or _('New')
        return super().create(vals_list)

    _sql_constraints = [
        ('uniq_company_idem', 'unique(company_id, idempotency_key)', 'Duplicate batch (idempotency).'),
    ]

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
                'request_json': safe_json_dumps(req or {}) if req else False,
                'response_json': safe_json_dumps(resp or {}) if resp else False,
            })

    def _get_connection(self):
        conn = self.env['finapify.connection'].search([
            ('company_id','=', self.company_id.id),
            ('user_id','=', self.env.user.id),
        ], limit=1)
        if not conn or not conn.is_connected:
            raise UserError(_('Finapify is not connected for this user/company.'))
        return conn

    def _get_n8n_url(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'finapify_payments.n8n_url',
            default='https://n8n.finapify.com/webhook-test/odoo'
        )

    def _compute_idempotency_key(self):
        self.ensure_one()
        parts = ["bulk", str(self.company_id.id), self.mode, str(self.currency_id.name), str(self.total_amount)]
        for ln in self.line_ids.sorted('vendor_bill_id'):
            parts.append(f"{ln.vendor_bill_id.id}:{ln.amount}:{ln.source_bank_id}:{ln.vendor_bank_id}")
        return sha256_hex('|'.join(parts))

    def action_submit_to_n8n(self, otp_value: str):
        self.ensure_one()
        
        # Check if Finapify API is authenticated
        check_finapify_authenticated(self.env)
        
        if self.status not in ('draft','review','otp_pending','failed'):
            raise UserError(_('This batch cannot be submitted in current state.'))

        if not self.line_ids:
            raise UserError(_('No lines to pay.'))

        conn = self._get_connection()
        jwt = conn.get_supabase_jwt()
        if not jwt:
            raise UserError(_('Supabase JWT missing.'))

        # validate journal mapping(s)
        source_bank_ids = set(self.line_ids.mapped('source_bank_id'))
        for sb in source_bank_ids:
            if not self.env['finapify.journal.map'].search([
                ('company_id','=', self.company_id.id),
                ('finapify_source_bank_id','=', sb),
                ('active','=', True)
            ], limit=1):
                raise UserError(_("Missing journal mapping for source bank_id: %s") % sb)

        correlation_id = self.correlation_id or generate_uuid()
        idem = self.idempotency_key or self._compute_idempotency_key()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        callback_url = f"{base_url}/finapify/callback"

        items = []
        for ln in self.line_ids:
            bill = ln.vendor_bill_id
            items.append({
                'bill_id': bill.id,
                'bill_name': bill.name,
                'vendor_id': ln.vendor_id.id,
                'vendor_name': ln.vendor_id.name,
                'amount': float(ln.amount),
                'vendor_bank_id': ln.vendor_bank_id,
                'source_bank_id': ln.source_bank_id,
            })

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
                'mode': 'bulk',
                'currency': self.currency_id.name,
                'total_amount': float(self.total_amount),
                'reference': self.name,
            },
            'items': items,
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
        self._log('initiate', 'info', 'Submitting batch to n8n', req=payload)

        status_code, data = http_post_json(n8n_url, headers=headers, payload=payload, timeout_s=60)
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

        if st in ('success','part_success'):
            self._apply_results_and_finalize(data)
        elif st == 'processing':
            self.write({'status': 'processing'})
        else:
            self.write({'status': 'failed', 'last_error': safe_json_dumps(data)})

    def _apply_results_and_finalize(self, data: dict):
        self.ensure_one()
        results = data.get('results') or []
        any_failed = False
        any_success = False

        # index lines by bill_id
        by_bill = {ln.vendor_bill_id.id: ln for ln in self.line_ids}

        for r in results:
            bid = int(r.get('bill_id') or 0)
            ln = by_bill.get(bid)
            if not ln:
                continue
            if r.get('status') == 'success':
                any_success = True
                ln._apply_success_result(r)
            else:
                any_failed = True
                ln.write({'status': 'failed', 'last_error': r.get('message') or 'Failed'})

        if any_success and any_failed:
            self.write({'status': 'part_success'})
        elif any_success and not any_failed:
            self.write({'status': 'success'})
        elif any_failed and not any_success:
            self.write({'status': 'failed'})
        else:
            self.write({'status': 'processing'})

        # attempt reconcile for all success lines
        for ln in self.line_ids.filtered(lambda x: x.status == 'success'):
            ln._attempt_reconcile()

        # compute batch reconciliation status
        if all(ln.reconciliation_status == 'reconciled' for ln in self.line_ids if ln.status == 'success'):
            self.write({'reconciliation_status': 'reconciled'})
        elif any(ln.reconciliation_status in ('partial','reconciled') for ln in self.line_ids):
            self.write({'reconciliation_status': 'partial'})

    def action_retry(self):
        self.ensure_one()
        if self.status not in ('failed','processing','part_success'):
            raise UserError(_('Only failed/processing batches can be retried.'))
        self.env['finapify.job'].sudo().enqueue_retry(self._name, self.id)
        self._log('retry', 'info', 'Enqueued retry job')

    def action_retry_reconcile(self):
        self.ensure_one()
        self.env['finapify.job'].sudo().enqueue_reconcile(self._name, self.id)
        self._log('reconcile', 'info', 'Enqueued reconcile job')


class FinapifyPaymentBatchLine(models.Model):
    _name = 'finapify.payment.batch.line'
    _description = 'Finapify Payment Batch Line'
    _order = 'id'

    batch_id = fields.Many2one('finapify.payment.batch', required=True, ondelete='cascade')
    vendor_bill_id = fields.Many2one('account.move', required=True, domain=[('move_type', 'in', ('in_invoice','in_refund'))])
    vendor_id = fields.Many2one('res.partner', related='vendor_bill_id.partner_id', store=True)

    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)

    vendor_bank_id = fields.Char(required=True)
    source_bank_id = fields.Char(required=True)

    status = fields.Selection([
        ('pending','Pending'),
        ('submitted','Submitted'),
        ('processing','Processing'),
        ('success','Success'),
        ('failed','Failed'),
    ], default='pending', index=True)

    finapify_ref = fields.Char(index=True)
    created_payment_ids = fields.Many2many('account.payment', string='Created Payments')

    reconciliation_status = fields.Selection([
        ('not_started','Not started'),
        ('partial','Partial'),
        ('reconciled','Reconciled'),
    ], default='not_started', index=True)

    last_error = fields.Text()

    def _apply_success_result(self, result: dict):
        self.ensure_one()
        fin_ref = result.get('finapify_ref')
        paid_amount = float(result.get('paid_amount') or self.amount)

        self.write({'status': 'success', 'finapify_ref': fin_ref})

        # global txn idempotency
        if fin_ref:
            existing_txn = self.env['finapify.txn'].search([
                ('company_id','=', self.batch_id.company_id.id),
                ('finapify_ref','=', fin_ref)
            ], limit=1)
            if existing_txn and existing_txn.payment_ids:
                self.write({'created_payment_ids': [(6, 0, existing_txn.payment_ids.ids)]})
                return

        payments = self._create_payment_for_success(paid_amount, fin_ref)

        if fin_ref:
            self.env['finapify.txn'].sudo().create({
                'company_id': self.batch_id.company_id.id,
                'finapify_ref': fin_ref,
                'request_model': self.batch_id._name,
                'request_id': self.batch_id.id,
                'payment_ids': [(6, 0, payments.ids)],
            })

        self.write({'created_payment_ids': [(6, 0, payments.ids)]})

    def _create_payment_for_success(self, paid_amount: float, finapify_ref: str):
        self.ensure_one()
        jm = self.env['finapify.journal.map'].search([
            ('company_id','=', self.batch_id.company_id.id),
            ('finapify_source_bank_id','=', self.source_bank_id),
            ('active','=', True)
        ], limit=1)
        if not jm:
            raise UserError(_("Missing journal mapping for source bank_id: %s") % self.source_bank_id)

        journal = jm.journal_id
        pml = journal.outbound_payment_method_line_ids[:1]
        if not pml:
            raise UserError(_('No outbound payment method line found on the selected journal.'))

        ref = f"Finapify {finapify_ref or ''} {self.vendor_bill_id.name}".strip()

        payment = self.env['account.payment'].create({
            'company_id': self.batch_id.company_id.id,
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.vendor_id.id,
            'amount': paid_amount,
            'currency_id': self.currency_id.id,
            'journal_id': journal.id,
            'payment_method_line_id': pml.id,
            'ref': ref,
        })
        payment.action_post()
        return payment

    def _attempt_reconcile(self):
        self.ensure_one()
        bill = self.vendor_bill_id
        if not self.created_payment_ids:
            self.write({'reconciliation_status': 'not_started'})
            return

        try:
            bill_lines = bill.line_ids.filtered(lambda l: l.account_id.account_type == 'liability_payable' and not l.reconciled)
            pay_lines = self.created_payment_ids.line_ids.filtered(lambda l: l.account_id.account_type == 'liability_payable' and not l.reconciled)
            lines = (bill_lines | pay_lines)
            if lines:
                lines.reconcile()

            if bill.amount_residual == 0:
                self.write({'reconciliation_status': 'reconciled'})
            else:
                self.write({'reconciliation_status': 'partial'})
        except Exception as e:
            self.write({'reconciliation_status': 'partial', 'last_error': str(e)})
