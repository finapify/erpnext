app_name = "finapify"
app_title = "Finapify"
app_publisher = "Finapify"
app_description = "ERP connected API banking solution provider. Now connect your bank account and make payments and reconcialation seamlessly within erpnext"
app_email = "developer@finapify.com"
app_license = "proprietary"

# Hooks
after_install = [
    "finapify.api.bank_account.setup_bank_account_fields",
    "finapify.finapify.doctype.finapify_user_type.finapify_user_type.create_default_user_types",
    "finapify.finapify.api.auth.enforce_mfa_for_system_users"
]

doctype_js = {
    "Purchase Order": "public/js/purchase_order_finapify.js",
    "Bank Account": "public/js/bank_account_finapify.js"
}
