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
