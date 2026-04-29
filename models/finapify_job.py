from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FinapifyJob(models.Model):
    _name = 'finapify.job'
    _description = 'Finapify Background Job'
    _order = 'run_at asc, id asc'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    job_type = fields.Selection([
        ('retry_payment','Retry Payment'),
        ('reconcile','Reconcile'),
    ], required=True)

    ref_model = fields.Char(required=True)
    ref_id = fields.Integer(required=True)

    run_at = fields.Datetime(required=True, default=fields.Datetime.now)
    attempts = fields.Integer(default=0)

    status = fields.Selection([
        ('queued','Queued'),
        ('running','Running'),
        ('done','Done'),
        ('failed','Failed'),
    ], default='queued', index=True)

    last_error = fields.Text()

    @api.model
    def enqueue_retry(self, ref_model: str, ref_id: int):
        return self.create({
            'company_id': self.env.company.id,
            'job_type': 'retry_payment',
            'ref_model': ref_model,
            'ref_id': ref_id,
            'run_at': fields.Datetime.now(),
        })

    @api.model
    def enqueue_reconcile(self, ref_model: str, ref_id: int):
        return self.create({
            'company_id': self.env.company.id,
            'job_type': 'reconcile',
            'ref_model': ref_model,
            'ref_id': ref_id,
            'run_at': fields.Datetime.now(),
        })

    @api.model
    def cron_process_jobs(self):
        now = fields.Datetime.now()
        jobs = self.search([('status','=','queued'), ('run_at','<=', now)], limit=50)
        for job in jobs:
            job._run_safe()

    def _run_safe(self):
        self.ensure_one()
        self.write({'status': 'running'})
        try:
            self._run()
            self.write({'status': 'done'})
        except Exception as e:
            attempts = self.attempts + 1
            self.write({'status': 'failed', 'attempts': attempts, 'last_error': str(e)})

            # schedule retry with backoff for retry_payment only
            if self.job_type == 'retry_payment' and attempts < 3:
                minutes = [5, 30, 120][attempts - 1]
                self.write({
                    'status': 'queued',
                    'run_at': fields.Datetime.now() + timedelta(minutes=minutes),
                })

    def _run(self):
        self.ensure_one()
        rec = self.env[self.ref_model].browse(self.ref_id).exists()
        if not rec:
            return

        # For retry_payment, we cannot re-submit without OTP.
        # Production pattern: re-submit requires a fresh OTP from user.
        # Here we do a safe retry behavior:
        # - If still processing: do nothing.
        # - If failed: keep failed and require user to retry from UI (OTP).
        # - For reconcile: attempt reconciliation.

        if self.job_type == 'reconcile':
            if self.ref_model == 'finapify.payment.request':
                rec._attempt_reconcile()
            elif self.ref_model == 'finapify.payment.batch':
                for ln in rec.line_ids.filtered(lambda x: x.status == 'success'):
                    ln._attempt_reconcile()
            return

        if self.job_type == 'retry_payment':
            # Just surface in logs; user must provide OTP.
            if hasattr(rec, '_log'):
                rec._log('retry', 'warn', 'Automatic retry requires OTP. Please retry from UI.')
            return
