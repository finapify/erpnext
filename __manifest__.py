{
    "name": "Finapify Payments",
    "version": "16.0.1.0.0",
    "category": "Accounting",
    "summary": "Pay vendor bills via Finapify (Supabase + n8n) with OTP, payments, and reconciliation.",
    "description": """
Production-ready integration to initiate vendor payments from Odoo using Finapify.

Key features:
- Connect Finapify (Supabase JWT + consent_id + linked bank accounts)
- Single and bulk vendor bill payments with OTP
- Async callbacks with HMAC verification
- Idempotency, retries with backoff, and audit logs
- Auto-create account.payment and reconcile to vendor bills
- Journal mapping from Finapify bank_id to Odoo bank journals
""",
    "author": "Finapify",
    "license": "LGPL-3",
    "depends": ["account", "purchase"],
    "data": [
        "security/ir.model.access.csv",
        "views/finapify_menus.xml",
        "views/finapify_dashboard_views.xml",
        "views/finapify_connection_views.xml",
        "views/finapify_vendor_map_views.xml",
        "views/finapify_journal_map_views.xml",
        "views/finapify_payment_request_views.xml",
        "views/finapify_payment_batch_views.xml",
        "views/finapify_log_views.xml",
        "views/finapify_reconciliation_views.xml",
        "views/account_move_inherit.xml",
        "views/purchase_order_inherit.xml",
        "views/res_partner_inherit.xml",
        "views/res_config_settings_views.xml",
        "wizards/finapify_connect_wizard_views.xml",
        "wizards/finapify_pay_single_wizard_views.xml",
        "wizards/finapify_pay_bulk_wizard_views.xml",
        "data/finapify_sequences.xml",
        "data/finapify_cron.xml",
    ],
    "installable": True,
    "application": True,
}
