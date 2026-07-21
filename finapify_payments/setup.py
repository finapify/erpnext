import frappe
from frappe import _
import uuid


def after_install():
    _create_default_settings()
    frappe.msgprint(_("Finapify Payments installed successfully!"))


def _create_default_settings():
    try:
        if not frappe.db.exists('Finapify Settings', 'Finapify Settings'):
            doc = frappe.get_doc({
                'doctype': 'Finapify Settings',
                'callback_secret': str(uuid.uuid4()).replace('-', ''),
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
    except Exception as e:
        frappe.log_error(str(e), "Finapify after_install")


def test_finapify_connection():
    """Sanity check run via `bench execute finapify_payments.setup.test_finapify_connection`."""
    if not frappe.db.exists('Finapify Settings', 'Finapify Settings'):
        print("FAIL: Finapify Settings singleton does not exist. Run after_install first.")
        return False

    settings = frappe.get_single('Finapify Settings')
    if not settings.callback_secret:
        print("FAIL: Finapify Settings has no callback_secret configured.")
        return False

    print("OK: Finapify Settings is present and configured.")
    print(f"  is_authenticated: {bool(settings.is_authenticated)}")
    print(f"  api_url: {settings.api_url}")
    return True
