app_name = "finapify_payments"
app_title = "Finapify Payments"
app_publisher = "Finapify"
app_description = "Pay vendor bills via Finapify (Supabase + n8n) with OTP, payments, and reconciliation."
app_email = "developer@finapify.com"
app_license = "LGPL-3"

# Requires ERPNext
required_apps = ["frappe", "erpnext"]

# After install
after_install = "finapify_payments.setup.after_install"

# Override ERPNext DocType controllers to add Finapify actions
override_doctype_class = {
    "Purchase Invoice": "finapify_payments.models.account_move_inherit.FinapifyPurchaseInvoice",
    "Purchase Order": "finapify_payments.models.purchase_order_inherit.FinapifyPurchaseOrder",
    "Supplier": "finapify_payments.models.res_partner_inherit.FinapifySupplier",
}

# Client-side scripts injected into standard ERPNext doctype forms
doctype_js = {
    "Purchase Invoice": "public/js/purchase_invoice.js",
}

# Scheduled Tasks
scheduler_events = {
    "all": [
        "finapify_payments.models.finapify_job.process_pending_payments",
        "finapify_payments.models.finapify_job.retry_failed_payments",
    ],
    "daily": [
        "finapify_payments.models.finapify_job.daily_sync_accounts",
    ],
    "weekly": [
        "finapify_payments.models.finapify_job.weekly_reconciliation",
    ],
}

# Fixtures — export Module Def so the module is registered on install
fixtures = [
    {"dt": "Module Def", "filters": [["module_name", "=", "Finapify Payments"]]},
]

# Jinja
jinja = {
    "methods": [],
    "filters": [],
}

# Website Route Rules — callback is exposed via @frappe.whitelist(allow_guest=True)
# accessible at /api/method/finapify_payments.controllers.main.finapify_callback
website_route_rules = []
