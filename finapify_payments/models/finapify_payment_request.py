import frappe
from frappe import _
from frappe.model.document import Document

from .utils import (
    generate_uuid, safe_json_dumps, mask_secrets,
    http_post_json, sha256_hex, check_finapify_authenticated,
)


class FinapifyPaymentRequest(Document):

    def _log(self, action, level='info', message=None, req=None, resp=None):
        try:
            frappe.get_doc({
                'doctype': 'Finapify Log',
                'company': self.company,
                'correlation_id': self.correlation_id or '',
                'model': self.doctype,
                'record_id': self.name,
                'action': action,
                'level': level,
                'message': message or '',
                'request_json': safe_json_dumps(mask_secrets(req or {})) if req else '',
                'response_json': safe_json_dumps(resp) if resp else '',
            }).insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Error logging payment request: {e}", 'Finapify Log Error')

    def _get_connection(self):
        name = frappe.db.get_value(
            'Finapify Connection',
            {'company': self.company, 'user': frappe.session.user},
            'name'
        )
        if not name:
            frappe.throw(_('Finapify is not connected for this user/company.'))

        conn = frappe.get_doc('Finapify Connection', name)
        if not conn.is_connected:
            frappe.throw(_('Finapify is not connected for this user/company.'))
        return conn

    def _get_n8n_url(self):
        return (
            frappe.db.get_single_value('Finapify Settings', 'n8n_url')
            or 'https://n8n.finapify.com/webhook-test/erpnext'
        )

    def _compute_idempotency_key(self):
        base = f"single|{self.company}|{self.vendor_bill}|{self.amount}|{self.currency}|{self.source_bank_id}|{self.vendor_bank_id}"
        return sha256_hex(base)

    @frappe.whitelist()
    def action_submit_to_n8n(self, otp_value: str):
        check_finapify_authenticated()

        if self.status not in ('Draft', 'Review', 'OTP Pending', 'Failed'):
            frappe.throw(_('This request cannot be submitted in current state.'))

        bill = frappe.get_doc('Purchase Invoice', self.vendor_bill)
        if bill.docstatus != 1:
            frappe.throw(_('Vendor bill must be submitted before payment.'))
        if not bill.outstanding_amount or bill.outstanding_amount <= 0:
            frappe.throw(_('Vendor bill has no outstanding amount.'))

        conn = self._get_connection()
        jwt = conn.get_supabase_jwt()
        if not jwt:
            frappe.throw(_('Supabase JWT missing. Reconnect Finapify.'))

        jm = frappe.db.get_value(
            'Finapify Journal Map',
            {'company': self.company, 'finapify_source_bank_id': self.source_bank_id},
            'name'
        )
        if not jm:
            frappe.throw(_('Map this Finapify Source Bank ID to a Mode of Payment in Finapify Settings.'))

        correlation_id = self.correlation_id or generate_uuid()
        idem = self.idempotency_key or self._compute_idempotency_key()
        callback_url = f"{frappe.utils.get_url()}/api/method/finapify_payments.controllers.main.finapify_callback"

        payload = {
            'product': 'frappe',
            'action': 'initiate_payment',
            'company': self.company,
            'user': frappe.session.user,
            'correlation_id': correlation_id,
            'idempotency_key': idem,
            'connection': {
                'consent_id': conn.consent_id,
                'default_source_bank_id': conn.default_source_bank_id or self.source_bank_id,
            },
            'otp': {'required': bool(self.otp_required), 'value': otp_value or ''},
            'payment': {
                'mode': 'single',
                'currency': self.currency,
                'total_amount': float(self.amount),
                'reference': self.name,
            },
            'items': [{
                'bill_id': self.vendor_bill,
                'vendor': self.vendor,
                'amount': float(self.amount),
                'vendor_bank_id': self.vendor_bank_id,
                'source_bank_id': self.source_bank_id,
            }],
            'callback': {
                'url': callback_url,
                'signature_type': 'hmac_sha256',
            },
        }

        headers = {'Authorization': f'Bearer {jwt}'}

        self.db_set('status', 'Submitted')
        self.db_set('correlation_id', correlation_id)
        self.db_set('idempotency_key', idem)
        self.db_set('request_payload_json', safe_json_dumps(payload))
        self.db_set('attempts', (self.attempts or 0) + 1)
        self._log('initiate', 'info', 'Submitting payment to n8n', req=payload)

        status_code, data = http_post_json(self._get_n8n_url(), headers=headers, payload=payload, timeout_s=45)

        self.db_set('response_payload_json', safe_json_dumps(data))
        if data.get('n8n_request_id'):
            self.db_set('n8n_request_id', data['n8n_request_id'])

        if status_code >= 400 or not data.get('ok', True):
            self.db_set('status', 'Failed')
            self.db_set('last_error', safe_json_dumps(data))
            self._log('initiate', 'error', 'n8n returned error', resp=data)
            return

        st = data.get('status')
        self._log('initiate', 'info', f'n8n status: {st}', resp=data)

        if st == 'success':
            self._apply_results_and_finalize(data)
        elif st in ('processing', 'part_success'):
            self.db_set('status', 'Processing')
        else:
            self.db_set('status', 'Failed')
            self.db_set('last_error', safe_json_dumps(data))

    def _apply_results_and_finalize(self, data: dict):
        results = data.get('results') or []
        if not results:
            self.db_set('status', 'Success')
            return

        match = None
        for r in results:
            if str(r.get('bill_id') or '') == str(self.vendor_bill):
                match = r
                break

        if not match:
            self.db_set('status', 'Processing')
            return

        if match.get('status') != 'success':
            self.db_set('status', 'Failed')
            self.db_set('last_error', match.get('message') or 'Payment failed')
            return

        fin_ref = match.get('finapify_ref')
        paid_amount = float(match.get('paid_amount') or self.amount)
        self.db_set('finapify_ref', fin_ref)
        self.db_set('status', 'Success')

        if fin_ref and frappe.db.exists('Finapify Txn', {'company': self.company, 'finapify_ref': fin_ref}):
            self._attempt_reconcile()
            return

        payment = self._create_payment_for_success(paid_amount, fin_ref)

        if fin_ref:
            frappe.get_doc({
                'doctype': 'Finapify Txn',
                'company': self.company,
                'finapify_ref': fin_ref,
                'request_model': self.doctype,
                'request_id': self.name,
            }).insert(ignore_permissions=True)

        if payment:
            self.db_set('created_payment', payment.name)
        self._attempt_reconcile()

    def _create_payment_for_success(self, paid_amount: float, finapify_ref: str):
        jm = frappe.db.get_value(
            'Finapify Journal Map',
            {'company': self.company, 'finapify_source_bank_id': self.source_bank_id},
            ['name', 'mode_of_payment', 'bank_account'],
            as_dict=True
        )
        if not jm:
            frappe.throw(_('Missing journal mapping for source bank ID.'))

        ref = f"Finapify {finapify_ref or ''} {self.vendor_bill}".strip()

        payment = frappe.new_doc('Payment Entry')
        payment.payment_type = 'Pay'
        payment.party_type = 'Supplier'
        payment.party = self.vendor
        payment.company = self.company
        payment.posting_date = frappe.utils.today()
        payment.paid_amount = paid_amount
        payment.received_amount = paid_amount
        payment.mode_of_payment = jm.mode_of_payment
        if jm.bank_account:
            payment.bank_account = jm.bank_account
        payment.reference_no = ref
        payment.reference_date = frappe.utils.today()
        payment.append('references', {
            'reference_doctype': 'Purchase Invoice',
            'reference_name': self.vendor_bill,
            'allocated_amount': paid_amount,
        })
        payment.insert(ignore_permissions=True)
        payment.submit()
        self._log('create_payment', 'info', f'Created payment {payment.name}')
        return payment

    def _attempt_reconcile(self):
        try:
            bill = frappe.get_doc('Purchase Invoice', self.vendor_bill)
            if not bill.outstanding_amount or bill.outstanding_amount == 0:
                self.db_set('reconciliation_status', 'Reconciled')
            else:
                self.db_set('reconciliation_status', 'Partial')
            self._log('reconcile', 'info', f'Reconciliation status: {self.reconciliation_status}')
        except Exception as e:
            self.db_set('reconciliation_status', 'Partial')
            self.db_set('last_error', str(e))
            self._log('reconcile', 'error', f'Reconcile failed: {e}')

    @frappe.whitelist()
    def action_retry(self):
        if self.status not in ('Failed', 'Processing'):
            frappe.throw(_('Only Failed or Processing requests can be retried.'))
        frappe.get_doc({
            'doctype': 'Finapify Job',
            'company': self.company,
            'job_type': 'Retry Payment',
            'ref_model': self.doctype,
            'ref_id': self.name,
            'run_at': frappe.utils.now(),
        }).insert(ignore_permissions=True)
        self._log('retry', 'info', 'Enqueued retry job')

    @frappe.whitelist()
    def action_retry_reconcile(self):
        frappe.get_doc({
            'doctype': 'Finapify Job',
            'company': self.company,
            'job_type': 'Reconcile',
            'ref_model': self.doctype,
            'ref_id': self.name,
            'run_at': frappe.utils.now(),
        }).insert(ignore_permissions=True)
        self._log('reconcile', 'info', 'Enqueued reconcile job')
