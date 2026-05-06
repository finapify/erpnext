import json

import frappe
from frappe import _

from ..models.utils import hmac_sha256_hex, safe_json_dumps


@frappe.whitelist(allow_guest=True)
def finapify_callback():
    """Receive async payment result from n8n and apply to matching request/batch."""
    try:
        raw = frappe.request.data or b''
        secret = frappe.db.get_single_value('Finapify Settings', 'callback_secret') or ''
        sig = frappe.get_request_header('X-Finapify-Signature') or ''

        if secret:
            calc = hmac_sha256_hex(secret, raw)
            if not sig or sig.lower() != calc.lower():
                frappe.log_error(
                    f'Invalid callback signature received: {sig}',
                    'Finapify Callback'
                )
                frappe.response.http_status_code = 401
                return {'status': 'error', 'message': 'Invalid signature'}

        try:
            payload = json.loads(raw.decode('utf-8') or '{}')
        except Exception:
            payload = {}

        n8n_request_id = payload.get('n8n_request_id')
        correlation_id = payload.get('correlation_id')
        status = payload.get('status')

        try:
            frappe.get_doc({
                'doctype': 'Finapify Log',
                'correlation_id': correlation_id or '',
                'action': 'callback',
                'level': 'info',
                'message': f'Callback received status={status}',
                'request_json': safe_json_dumps(payload),
            }).insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as log_err:
            frappe.log_error(str(log_err), 'Finapify Callback Log Error')

        req_rec = None
        batch_rec = None

        if n8n_request_id:
            req_name = frappe.db.get_value(
                'Finapify Payment Request', {'n8n_request_id': n8n_request_id}, 'name'
            )
            if req_name:
                req_rec = frappe.get_doc('Finapify Payment Request', req_name)

            batch_name = frappe.db.get_value(
                'Finapify Payment Batch', {'n8n_request_id': n8n_request_id}, 'name'
            )
            if batch_name:
                batch_rec = frappe.get_doc('Finapify Payment Batch', batch_name)

        if not req_rec and correlation_id:
            req_name = frappe.db.get_value(
                'Finapify Payment Request', {'correlation_id': correlation_id}, 'name'
            )
            if req_name:
                req_rec = frappe.get_doc('Finapify Payment Request', req_name)

        if not batch_rec and correlation_id:
            batch_name = frappe.db.get_value(
                'Finapify Payment Batch', {'correlation_id': correlation_id}, 'name'
            )
            if batch_name:
                batch_rec = frappe.get_doc('Finapify Payment Batch', batch_name)

        if req_rec:
            req_rec.db_set('response_payload_json', safe_json_dumps(payload))
            if status in ('success', 'part_success'):
                req_rec._apply_results_and_finalize(payload)
            elif status == 'failed':
                req_rec.db_set('status', 'Failed')
                req_rec.db_set('last_error', safe_json_dumps(payload))
            else:
                req_rec.db_set('status', 'Processing')

        if batch_rec:
            batch_rec.db_set('response_payload_json', safe_json_dumps(payload))
            if status in ('success', 'part_success'):
                batch_rec._apply_results_and_finalize(payload)
            elif status == 'failed':
                batch_rec.db_set('status', 'Failed')
                batch_rec.db_set('last_error', safe_json_dumps(payload))
            else:
                batch_rec.db_set('status', 'Processing')

        frappe.db.commit()
        return {'status': 'ok'}

    except Exception as e:
        frappe.log_error(str(e), 'Finapify Callback Error')
        frappe.response.http_status_code = 500
        return {'status': 'error', 'message': str(e)}


@frappe.whitelist()
def get_dashboard_data():
    """Return dashboard statistics for the Finapify dashboard page."""
    company = frappe.defaults.get_user_default('company') or frappe.db.get_single_value('Global Defaults', 'default_company')

    try:
        is_authenticated = bool(frappe.db.get_single_value('Finapify Settings', 'is_authenticated'))

        return {
            'success': True,
            'data': {
                'is_authenticated': is_authenticated,
                'total_connections': frappe.db.count('Finapify Connection', {'company': company}),
                'pending_requests': frappe.db.count('Finapify Payment Request', {'company': company, 'status': 'Draft'}),
                'processing_requests': frappe.db.count('Finapify Payment Request', {'company': company, 'status': 'Processing'}),
                'completed_batches': frappe.db.count('Finapify Payment Batch', {'company': company, 'status': 'Success'}),
                'failed_batches': frappe.db.count('Finapify Payment Batch', {'company': company, 'status': 'Failed'}),
                'total_vendor_mappings': frappe.db.count('Finapify Vendor Bank Map', {'company': company}),
                'total_journal_mappings': frappe.db.count('Finapify Journal Map', {'company': company}),
            },
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def authenticate_finapify(api_key=None, api_secret=None):
    """Test Finapify API authentication and store result in Finapify Settings."""
    import requests as req_lib

    if not api_key or not api_secret:
        return {'success': False, 'error': 'API key and secret are required'}

    try:
        icp = frappe.get_doc('Finapify Settings', 'Finapify Settings')
        icp.db_set('api_key', api_key)
        icp.db_set('api_secret', api_secret)

        api_url = frappe.db.get_single_value('Finapify Settings', 'api_url') or 'https://api.finapify.com/webhook/erpnext'
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
        response = req_lib.get(f'{api_url}/health', headers=headers, timeout=10)

        if response.status_code == 200:
            icp.db_set('is_authenticated', 1)
            icp.db_set('last_auth_at', frappe.utils.now())
            icp.db_set('auth_error', '')

            frappe.get_doc({
                'doctype': 'Finapify Log',
                'action': 'api_auth',
                'level': 'info',
                'message': 'API authentication successful',
            }).insert(ignore_permissions=True)

            return {'success': True, 'message': 'Authentication successful!'}
        else:
            icp.db_set('is_authenticated', 0)
            icp.db_set('auth_error', response.text or f'HTTP {response.status_code}')
            return {'success': False, 'error': f'Authentication failed with status {response.status_code}'}

    except req_lib.exceptions.RequestException as e:
        return {'success': False, 'error': f'Connection error: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
