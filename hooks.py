app_name = "finapify_payments"
app_title = "Finapify Payments"
app_publisher = "Finapify"
app_description = "Pay vendor bills via Finapify (Supabase + n8n) with OTP, payments, and reconciliation."
app_email = "developer@finapify.com"
app_license = "LGPL-3"
app_version = "16.0.1.0.0"

# Requires
requires = ["erpnext", "frappe"]

# Doctype Setup
setup_wizard_requires = "erpnext.setup.setup_wizard"

# Auto Install
auto_install = False
install_after = ["erpnext"]

# Fixtures
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [["dt", "in", ["Purchase Invoice", "Purchase Order", "Supplier"]]]
    },
    {
        "doctype": "Property Setter",
        "filters": [["doc_type", "in", ["Purchase Invoice", "Purchase Order", "Supplier"]]]
    }
]

# Doctype List
doctype_list_js = {}
doctype_tree_js = {}
doctype_calendar_js = {}

# Document Events
doc_events = {}

# Page Events  
page_events = {}

# Before Install
before_install = []

# After Install
after_install = [
    "finapify_payments.setup.after_install"
]

# Before Uninstall
before_uninstall = []

# After Uninstall
after_uninstall = []

# Migrate
migrate = []

# on_session_creation
on_session_creation = []

# Scheduled Tasks (Cron)
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
    ]
}

# Jinja
jinja = {
    "methods": [],
    "filters": [],
}

# Middleware
website_context = {}
website_route_rules = []

# Override
override_doctype_class = {
    "Purchase Invoice": "finapify_payments.models.account_move_inherit.FinapifyPurchaseInvoice",
    "Purchase Order": "finapify_payments.models.purchase_order_inherit.FinapifyPurchaseOrder",
    "Supplier": "finapify_payments.models.res_partner_inherit.FinapifySupplier",
}

# Include JS
app_include_js = []

# Include CSS
app_include_css = [
    "/assets/finapify_payments/css/finapify_dashboard.css"
]

# WWW (Website)
www_data = []

# Website Route Rules
website_route_rules = []

# User Permissions
user_data_fields = [
    {
        "doctype": "{doctype_name}",
        "field_name": "owner",
        "standard_filter": 1
    },
]

# Links
has_permission = {}
has_website_permission = {}
