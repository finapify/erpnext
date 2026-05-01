import json

from odoo import http
from odoo.http import request

from ..models.utils import hmac_sha256_hex, safe_json_dumps


class FinapifyCallbackController(http.Controller):

    @http.route('/finapify/callback', type='http', auth='public', methods=['POST'], csrf=False)
    def finapify_callback(self, **kwargs):
        raw = request.httprequest.data or b''

        secret = request.env['ir.config_parameter'].sudo().get_param('finapify_payments.callback_secret') or ''
        sig = request.httprequest.headers.get('X-Finapify-Signature') or ''

        # Verify signature
        if secret:
            calc = hmac_sha256_hex(secret, raw)
            if not sig or sig.lower() != calc.lower():
                request.env['finapify.log'].sudo().create({
                    'company_id': request.env.company.id,
                    'action': 'callback',
                    'level': 'error',
                    'message': 'Invalid callback signature',
                    'request_json': safe_json_dumps({'headers': dict(request.httprequest.headers)}),
                    'response_json': safe_json_dumps({'calc': calc, 'sig': sig}),
                })
                return request.make_response('invalid signature', headers=[('Content-Type','text/plain')], status=401)

        try:
            payload = json.loads(raw.decode('utf-8') or '{}')
        except Exception:
            payload = {}

        n8n_request_id = payload.get('n8n_request_id')
        correlation_id = payload.get('correlation_id')
        status = payload.get('status')
        results = payload.get('results') or []

        # Try to match request or batch
        env = request.env

        req_rec = None
        batch_rec = None

        if n8n_request_id:
            req_rec = env['finapify.payment.request'].sudo().search([('n8n_request_id','=', n8n_request_id)], limit=1)
            batch_rec = env['finapify.payment.batch'].sudo().search([('n8n_request_id','=', n8n_request_id)], limit=1)

        if not req_rec and correlation_id:
            req_rec = env['finapify.payment.request'].sudo().search([('correlation_id','=', correlation_id)], limit=1)
        if not batch_rec and correlation_id:
            batch_rec = env['finapify.payment.batch'].sudo().search([('correlation_id','=', correlation_id)], limit=1)

        # Log callback
        env['finapify.log'].sudo().create({
            'company_id': env.company.id,
            'correlation_id': correlation_id,
            'action': 'callback',
            'level': 'info',
            'message': f'Callback received status={status}',
            'request_json': safe_json_dumps(payload),
        })

        # Apply
        if req_rec:
            # Update stored response
            req_rec.write({'response_payload_json': safe_json_dumps(payload)})
            if status in ('success','part_success'):
                req_rec._apply_results_and_finalize(payload)
            elif status == 'failed':
                req_rec.write({'status': 'failed', 'last_error': safe_json_dumps(payload)})
            else:
                req_rec.write({'status': 'processing'})

        if batch_rec:
            batch_rec.write({'response_payload_json': safe_json_dumps(payload)})
            if status in ('success','part_success'):
                batch_rec._apply_results_and_finalize(payload)
            elif status == 'failed':
                batch_rec.write({'status': 'failed', 'last_error': safe_json_dumps(payload)})
            else:
                batch_rec.write({'status': 'processing'})

        return request.make_response('ok', headers=[('Content-Type','text/plain')], status=200)


class FinapifyDashboardController(http.Controller):

    @http.route('/finapify/dashboard/data', type='json', auth='user', methods=['GET'])
    def get_dashboard_data(self):
        """Get dashboard statistics and quick info"""
        env = request.env
        company_id = env.company.id

        try:
            # Check authentication status
            icp = env['ir.config_parameter'].sudo()
            is_authenticated = icp.get_param('finapify_payments.is_authenticated', default='False') == 'True'
            
            # Count total connections
            total_connections = env['finapify.connection'].search_count(
                [('company_id', '=', company_id)]
            )
            
            # Count pending payment requests
            pending_requests = env['finapify.payment.request'].search_count(
                [('company_id', '=', company_id), ('state', '=', 'pending')]
            )
            
            # Count processing payment requests
            processing_requests = env['finapify.payment.request'].search_count(
                [('company_id', '=', company_id), ('state', '=', 'processing')]
            )
            
            # Count completed batches
            completed_batches = env['finapify.payment.batch'].search_count(
                [('company_id', '=', company_id), ('state', '=', 'completed')]
            )
            
            # Count failed batches
            failed_batches = env['finapify.payment.batch'].search_count(
                [('company_id', '=', company_id), ('state', '=', 'failed')]
            )
            
            # Get total vendor mappings
            total_vendor_mappings = env['finapify.vendor.bank.map'].search_count(
                [('company_id', '=', company_id)]
            )
            
            # Get total journal mappings
            total_journal_mappings = env['finapify.journal.map'].search_count(
                [('company_id', '=', company_id)]
            )

            return {
                'success': True,
                'data': {
                    'is_authenticated': is_authenticated,
                    'total_connections': total_connections,
                    'pending_requests': pending_requests,
                    'processing_requests': processing_requests,
                    'completed_batches': completed_batches,
                    'failed_batches': failed_batches,
                    'total_vendor_mappings': total_vendor_mappings,
                    'total_journal_mappings': total_journal_mappings,
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/finapify/dashboard/authenticate', type='json', auth='user', methods=['POST'])
    def authenticate_finapify(self, api_key=None, api_secret=None):
        """Test Finapify API authentication"""
        env = request.env
        company_id = env.company.id

        if not api_key or not api_secret:
            return {
                'success': False,
                'error': 'API key and secret are required'
            }

        try:
            # Store credentials temporarily for testing
            icp = env['ir.config_parameter'].sudo()
            icp.set_param('finapify_payments.api_key', api_key)
            icp.set_param('finapify_payments.api_secret', api_secret)

            # Test API connection
            api_url = icp.get_param('finapify_payments.api_url', default='https://api.finapify.com/webhook/erpnext')
            
            import requests
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }
            
            # Try a health check endpoint
            response = requests.get(f'{api_url}/health', headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Log successful authentication
                env['finapify.log'].sudo().create({
                    'company_id': company_id,
                    'action': 'api_auth',
                    'level': 'info',
                    'message': 'API authentication successful',
                })
                return {
                    'success': True,
                    'message': 'Authentication successful!',
                    'status': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': f'Authentication failed with status {response.status_code}',
                    'details': response.text
                }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Connection error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

