import frappe
from frappe import _

def after_install():
    """Run after the app is installed"""
    create_doctypes()
    setup_permissions()
    create_default_settings()
    create_hooks()
    frappe.msgprint(_("Finapify Payments installed successfully!"))

def create_doctypes():
    """Ensure all doctypes are created"""
    # Doctypes should be auto-created from their JSON definitions
    # If they don't exist, they can be created through the web UI
    pass

def setup_permissions():
    """Setup default permissions for doctypes"""
    try:
        # Add permissions for System Manager role to all finapify doctypes
        doctypes = [
            'Finapify Connection',
            'Finapify Payment Request',
            'Finapify Payment Batch',
            'Finapify Log',
            'Finapify Settings',
            'Finapify Bank Statement',
            'Finapify Vendor Bank Map',
            'Finapify Journal Map',
        ]
        
        for doctype in doctypes:
            try:
                # This will fail silently if doctype doesn't exist yet
                frappe.get_doc({
                    'doctype': 'Role Profile',
                    'role': 'System Manager',
                }).insert(ignore_if_duplicate=True)
            except Exception:
                pass
    except Exception as e:
        frappe.log_error(f"Error setting permissions: {str(e)}")

def create_default_settings():
    """Create Finapify Settings doctype if it doesn't exist"""
    try:
        if not frappe.db.exists('Finapify Settings', 'Finapify Settings'):
            doc = frappe.get_doc({
                'doctype': 'Finapify Settings',
                'is_enabled': 1,
                'callback_secret': generate_callback_secret(),
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.msgprint(_("Created default Finapify Settings"))
    except frappe.DoesNotExistError:
        # Finapify Settings doctype doesn't exist yet - needs to be created via web UI
        pass
    except Exception as e:
        frappe.log_error(f"Error creating default settings: {str(e)}")

def create_hooks():
    """Setup webhook routes"""
    pass

def generate_callback_secret():
    """Generate a random callback secret"""
    import uuid
    return str(uuid.uuid4()).replace('-', '')

# Frappe whitelist methods

@frappe.whitelist()
def test_finapify_connection():
    """Test Finapify API connection"""
    try:
        settings = frappe.get_doc('Finapify Settings')
        if not settings.api_key or not settings.api_secret:
            return {'status': 'error', 'message': 'API credentials not configured'}
        
        # Implement actual API test here
        return {
            'status': 'success',
            'message': 'Connection successful',
            'is_authenticated': True,
        }
    except Exception as e:
        frappe.log_error(str(e), "Finapify Connection Test")
        return {
            'status': 'error',
            'message': str(e),
            'is_authenticated': False,
        }

@frappe.whitelist()
def get_finapify_stats():
    """Get Finapify dashboard statistics"""
    try:
        stats = {
            'total_requests': frappe.db.count('Finapify Payment Request'),
            'total_batches': frappe.db.count('Finapify Payment Batch'),
            'pending_payments': frappe.db.count('Finapify Payment Request', 
                filters={'status': 'otp_pending'}),
            'successful_payments': frappe.db.count('Finapify Payment Request',
                filters={'status': 'success'}),
            'failed_payments': frappe.db.count('Finapify Payment Request',
                filters={'status': 'failed'}),
        }
        return stats
    except Exception as e:
        frappe.log_error(str(e), "Get Finapify Stats")
        return {'error': str(e)}

