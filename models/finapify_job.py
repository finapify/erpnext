from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class FinapifyJob(Document):

    def run_safe(self):
        self.db_set('status', 'Running')
        try:
            self._run()
            self.db_set('status', 'Done')
        except Exception as e:
            attempts = (self.attempts or 0) + 1
            self.db_set('attempts', attempts)
            self.db_set('last_error', str(e))

            if self.job_type == 'Retry Payment' and attempts < 3:
                minutes = [5, 30, 120][attempts - 1]
                self.db_set('status', 'Queued')
                self.db_set('run_at', str(now_datetime() + timedelta(minutes=minutes)))
            else:
                self.db_set('status', 'Failed')

    def _run(self):
        if not frappe.db.exists(self.ref_model, self.ref_id):
            return

        rec = frappe.get_doc(self.ref_model, self.ref_id)

        if self.job_type == 'Reconcile':
            if self.ref_model == 'Finapify Payment Request':
                rec._attempt_reconcile()
            elif self.ref_model == 'Finapify Payment Batch':
                for ln in rec.line_ids:
                    if ln.status == 'Success':
                        ln._attempt_reconcile()
            return

        if self.job_type == 'Retry Payment':
            if hasattr(rec, '_log'):
                rec._log('retry', 'warn', 'Automatic retry requires OTP. Please retry from UI.')
            return


# --- Scheduled task functions referenced in hooks.py ---

def process_pending_payments():
    """Process queued Finapify Jobs."""
    now = frappe.utils.now()
    jobs = frappe.get_list(
        'Finapify Job',
        filters={'status': 'Queued', 'run_at': ['<=', now]},
        fields=['name'],
        limit=50,
        order_by='run_at asc',
    )
    for j in jobs:
        try:
            doc = frappe.get_doc('Finapify Job', j.name)
            doc.run_safe()
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(str(e), 'Finapify Job Error')


def retry_failed_payments():
    """Re-queue failed Retry Payment jobs within the retry window."""
    jobs = frappe.get_list(
        'Finapify Job',
        filters={'status': 'Failed', 'attempts': ['<', 3], 'job_type': 'Retry Payment'},
        fields=['name', 'attempts'],
        limit=20,
    )
    for j in jobs:
        try:
            attempts = j.attempts or 0
            minutes = [5, 30, 120][min(attempts, 2)]
            frappe.db.set_value('Finapify Job', j.name, {
                'status': 'Queued',
                'run_at': str(now_datetime() + timedelta(minutes=minutes)),
            })
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(str(e), 'Finapify Retry Failed')


def daily_sync_accounts():
    """Refresh bank accounts for all active Finapify connections."""
    connections = frappe.get_list(
        'Finapify Connection',
        filters={'is_connected': 1},
        fields=['name'],
    )
    for c in connections:
        try:
            doc = frappe.get_doc('Finapify Connection', c.name)
            doc.action_refresh_accounts()
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(str(e), 'Finapify Daily Sync')


def weekly_reconciliation():
    """Attempt reconciliation on all Partial requests and batches."""
    for model in ('Finapify Payment Request', 'Finapify Payment Batch'):
        records = frappe.get_list(
            model,
            filters={'reconciliation_status': 'Partial', 'status': 'Success'},
            fields=['name'],
        )
        for r in records:
            try:
                doc = frappe.get_doc(model, r.name)
                if model == 'Finapify Payment Request':
                    doc._attempt_reconcile()
                else:
                    for ln in doc.line_ids:
                        if ln.status == 'Success':
                            ln._attempt_reconcile()
                frappe.db.commit()
            except Exception as e:
                frappe.log_error(str(e), 'Finapify Weekly Reconcile')
