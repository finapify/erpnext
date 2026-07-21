import json

import frappe
from frappe import _
from frappe.model.document import Document


class FinapifyBankStatement(Document):

    def validate(self):
        if self.date_from and self.date_to and str(self.date_from) > str(self.date_to):
            frappe.throw(_('From Date cannot be after To Date.'))

    @frappe.whitelist()
    def get_available_banks(self):
        conn = frappe.db.get_value(
            'Finapify Connection',
            {'company': self.company},
            'bank_accounts_json'
        )
        if not conn:
            return []
        try:
            accounts = json.loads(conn)
            return [
                {
                    'id': acc.get('bank_id'),
                    'name': f"{acc.get('bank_name', 'Unknown')} ({acc.get('account_number', '')})",
                }
                for acc in accounts
            ]
        except Exception:
            return []

    @frappe.whitelist()
    def fetch_bank_statement(self):
        import requests

        if self.state != 'Draft':
            frappe.throw(_('Statement must be in Draft state to fetch.'))

        if not self.bank_id or not self.date_from or not self.date_to:
            frappe.throw(_('Bank ID, From Date, and To Date are required.'))

        from .utils import check_finapify_authenticated
        check_finapify_authenticated()

        conn = frappe.db.get_value(
            'Finapify Connection',
            {'company': self.company},
            ['name', 'is_connected', 'consent_id'],
            as_dict=True
        )
        if not conn or not conn.is_connected:
            frappe.throw(_('Finapify connection is not active. Please reconnect.'))

        conn_doc = frappe.get_doc('Finapify Connection', conn.name)
        jwt = conn_doc.get_supabase_jwt()
        if not jwt:
            frappe.throw(_('Supabase JWT missing. Reconnect Finapify.'))

        try:
            self.db_set('state', 'Fetching')

            api_url = (
                frappe.db.get_single_value('Finapify Settings', 'api_url')
                or 'https://api.finapify.com/webhook/erpnext'
            )
            headers = {
                'Authorization': f'Bearer {jwt}',
                'Content-Type': 'application/json',
            }
            payload = {
                'bank_id': self.bank_id,
                'date_from': str(self.date_from),
                'date_to': str(self.date_to),
                'consent_id': conn.consent_id,
            }

            response = requests.post(f'{api_url}/bank-statements', headers=headers, json=payload, timeout=30)
            try:
                response_data = response.json()
            except Exception:
                response_data = {'_raw': response.text}

            self.db_set('response_json', json.dumps(response_data, indent=2))

            if response.status_code == 200:
                transactions = response_data.get('transactions', [])

                frappe.db.delete('Finapify Bank Statement Line', {'parent': self.name})

                for txn in transactions:
                    amount = float(txn.get('amount', 0))
                    line = frappe.new_doc('Finapify Bank Statement Line')
                    line.parent = self.name
                    line.parenttype = self.doctype
                    line.parentfield = 'line_ids'
                    line.transaction_date = txn.get('date')
                    line.description = txn.get('description', '')
                    line.reference = txn.get('reference', '')
                    line.transaction_type = 'Debit' if amount < 0 else 'Credit'
                    line.amount = abs(amount)
                    line.balance = float(txn.get('balance', 0))
                    line.counterparty_name = txn.get('counterparty_name', '')
                    line.counterparty_account = txn.get('counterparty_account', '')
                    line.raw_json = json.dumps(txn)
                    line.insert(ignore_permissions=True)

                self.db_set('state', 'Loaded')
                self.db_set('fetched_at', frappe.utils.now())
                self.db_set('error_message', '')

                frappe.get_doc({
                    'doctype': 'Finapify Log',
                    'company': self.company,
                    'action': 'bank_statement_fetch',
                    'level': 'info',
                    'message': f'Bank statement fetched: {len(transactions)} transactions',
                }).insert(ignore_permissions=True)

                frappe.msgprint(
                    _('Bank statement fetched successfully with {0} transactions.').format(len(transactions)),
                    alert=True,
                    indicator='green'
                )
                return True

            else:
                error_msg = response_data.get('error', f'HTTP {response.status_code}')
                self.db_set('state', 'Failed')
                self.db_set('error_message', error_msg)

                frappe.get_doc({
                    'doctype': 'Finapify Log',
                    'company': self.company,
                    'action': 'bank_statement_fetch',
                    'level': 'error',
                    'message': f'Bank statement fetch failed: {error_msg}',
                }).insert(ignore_permissions=True)

                frappe.throw(_('API Error: %s') % error_msg)

        except requests.exceptions.Timeout:
            self.db_set('state', 'Failed')
            self.db_set('error_message', 'Request timeout')
            frappe.throw(_('Request timeout while fetching bank statement.'))

        except requests.exceptions.RequestException as e:
            self.db_set('state', 'Failed')
            self.db_set('error_message', str(e))
            frappe.throw(_('Connection error: %s') % str(e))

        except frappe.ValidationError:
            raise

        except Exception as e:
            self.db_set('state', 'Failed')
            self.db_set('error_message', str(e))
            frappe.throw(_('Error: %s') % str(e))

    @frappe.whitelist()
    def action_reload_statement(self):
        self.db_set('state', 'Draft')
        return self.fetch_bank_statement()

    @frappe.whitelist()
    def action_set_draft(self):
        self.db_set('state', 'Draft')


class FinapifyBankStatementLine(Document):

    @frappe.whitelist()
    def action_match_payment(self):
        return {
            'doctype': 'Payment Entry',
            'filters': {
                'payment_type': 'Pay',
                'docstatus': 0,
                'paid_amount': self.amount,
            },
        }

    def reconcile_with_payment(self, payment_name):
        if payment_name:
            self.db_set('matched_payment', payment_name)
            self.db_set('reconciliation_status', 'Reconciled')
