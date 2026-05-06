# Migration Guide: From Mixed Odoo/Frappe to Pure ERPNext

This document describes how we converted the finapify_payments module from a mixed Odoo/Frappe codebase to a pure Frappe/ERPNext implementation.

## What Was Fixed

### 1. **Framework Conversion**

| Aspect | Before (Odoo) | After (Frappe/ERPNext) |
|--------|---------------|------------------------|
| Imports | `from odoo import api, fields, models` | `import frappe` |
| Models | `models.Model`, `models.TransientModel` | `frappe.model.document.Document` |
| Database | ORM with `create()`, `write()` | Document API with `insert()`, `db_set()` |
| Views | XML with Odoo schema | JSON or XML with Frappe schema |
| Controllers | `http.Controller`, `@http.route` | `@frappe.whitelist()` methods |
| Config | `__manifest__.py` | `hooks.py` |

### 2. **Key Changes Made**

#### `hooks.py` Created
- Replaced `__manifest__.py` with proper Frappe `hooks.py`
- Defined doctypes, fixtures, scheduled events
- Added after_install hooks
- Configured override classes

#### Model Files Converted
- `finapify_connection.py` - Now uses `Document` base class
- `finapify_payment_request.py` - Converted to Frappe Document
- `finapify_payment_batch.py` - Frappe-compatible
- `finapify_log.py` - Document-based
- All model files use Frappe imports

#### Utilities Updated
- `models/utils.py` - Updated all Odoo imports to Frappe
- `encryption.py` - Uses Frappe utilities
- `http_post_json()` - Works with Frappe context
- Authentication helpers refactored for Frappe

#### Controllers Converted
- `controllers/main.py` - Changed from `http.Controller` to `@frappe.whitelist()`
- `finapify_callback()` - Now a Frappe method, not an HTTP route
- Webhook handling adapted for Frappe

#### Setup Scripts
- `setup.py` - Created with proper Frappe after_install hooks
- Installation procedures adapted for Frappe
- Permission setup for Frappe roles

### 3. **API Compatibility**

#### OLD (Odoo) API
```python
from odoo import api, fields, models

class FinapifyConnection(models.Model):
    _name = 'finapify.connection'
    name = fields.Char()
    
    @api.model_create_multi
    def create(self, vals_list):
        pass
```

#### NEW (Frappe) API
```python
import frappe
from frappe.model.document import Document

class FinapifyConnection(Document):
    def validate(self):
        pass
    
    def on_insert(self):
        pass
```

## Database Migration Steps

If migrating from an Odoo database to ERPNext:

### 1. **Backup Existing Data**
```bash
# Odoo database backup
mysqldump -u root -p odoo_database > odoo_backup.sql

# ERPNext database backup (if exists)
mysqldump -u root -p frappe_database > frappe_backup.sql
```

### 2. **Export Finapify Data from Odoo**
```bash
# Create SQL export of Finapify tables
mysql -u root -p odoo_database -e "
SELECT * INTO OUTFILE '/tmp/connections.csv'
FIELDS TERMINATED BY ','
FROM finapify_connection;
"
```

### 3. **Import into ERPNext**

Create Frappe doctypes first, then:

```python
# Import script - execute via bench
import frappe
import csv

with open('/path/to/connections.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        doc = frappe.get_doc({
            'doctype': 'Finapify Connection',
            'name': row['id'],
            'company': row['company_id'],
            'supabase_user_id': row['supabase_user_id'],
            # ... map other fields
        })
        doc.insert()
```

## File Structure Changes

### Before (Mixed)
```
finapify_payments/
├── __manifest__.py (Odoo)
├── __init__.py
├── models/
│   ├── finapify_connection.py (Odoo model)
│   ├── finapify_payment_request.py (Odoo model)
│   └── ...
├── controllers/
│   ├── main.py (Odoo HTTP controller)
│   └── ...
└── finapify/ (Frappe module - subdirectory)
    ├── hooks.py
    ├── api/
    └── ...
```

### After (Pure Frappe)
```
finapify_payments/
├── hooks.py (Frappe)
├── setup.py (Frappe setup)
├── __init__.py
├── models/
│   ├── finapify_connection.py (Frappe Document)
│   ├── finapify_payment_request.py (Frappe Document)
│   └── ...
├── controllers/
│   ├── main.py (Frappe whitelist methods)
│   └── ...
├── wizards/ (Frappe wizards)
├── views/ (Frappe views)
├── data/ (Frappe data)
├── README.md
└── INSTALLATION.md
```

## Import Changes Summary

### Framework Imports
```python
# OLD
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo import http

# NEW
import frappe
from frappe import _
from frappe.exceptions import ValidationError
from frappe.model.document import Document
from frappe.utils import get_request_header
```

### ORM Changes
```python
# OLD - Odoo ORM
class FinapifyLog(models.Model):
    _name = 'finapify.log'
    company_id = fields.Many2one('res.company')
    message = fields.Char()
    
    def create(self, vals_list):
        return super().create(vals_list)

# NEW - Frappe Document
class FinapifyLog(Document):
    def validate(self):
        pass
    
    def on_insert(self):
        pass
```

### Database Operations
```python
# OLD - Odoo
self.env['finapify.log'].search([('company_id','=', company_id)])
rec.write({'status': 'completed'})

# NEW - Frappe
frappe.db.get_list('Finapify Log', {'company': company_id})
doc.db_set('status', 'completed')
```

### HTTP Endpoints
```python
# OLD - Odoo
from odoo import http

class FinapifyController(http.Controller):
    @http.route('/finapify/callback', type='http', auth='public', csrf=False)
    def callback(self, **kwargs):
        return 'ok'

# NEW - Frappe
@frappe.whitelist(allow_guest=True)
def finapify_callback():
    return {'status': 'ok'}
```

## Testing the Migration

### 1. **Verify All Imports**
```bash
# Should return nothing if migration is complete
grep -r "from odoo import" ~/frappe-bench/apps/finapify_payments/
grep -r "models.Model" ~/frappe-bench/apps/finapify_payments/
```

### 2. **Check for Syntax Errors**
```bash
cd ~/frappe-bench
bench --site site1.local execute finapify_payments.setup.test_finapify_connection
```

### 3. **Verify Doctypes Load**
```bash
bench --site site1.local migrate
bench --site site1.local clear-cache
# Then check ERPNext web UI for Finapify doctypes
```

### 4. **Test Callbacks**
```bash
# Create a test payment request
# The callback endpoint should work without errors
```

## Remaining Tasks

### Before Production Deployment

1. **Create Doctype JSON Files**
   - Define field types and validation rules
   - Add custom buttons and actions
   - Configure access control

2. **Add Security Customizations**
   - Create role-based permissions
   - Add document-level security
   - Configure audit trail

3. **Create Views (XMLs)**
   - List views
   - Form views
   - Report views

4. **Add Custom Fields**
   - Extend Account Move with Finapify fields
   - Extend Purchase Order with payment options
   - Extend Res Partner with bank details

5. **Setup Background Jobs**
   - Configure scheduled cron jobs
   - Setup background workers for retries
   - Configure logging

6. **Create Integration Tests**
   - Test payment flows
   - Test callback handling
   - Test error scenarios

## Troubleshooting Migration

### Issue: "ModuleNotFoundError: No module named 'odoo'"
**Solution:** Ensure all `from odoo` imports are removed. Use `import frappe` instead.

### Issue: "Document has no attribute 'env'"
**Solution:** Replace `self.env` with `frappe`. Example: `self.env.company` → `frappe.defaults.get_user_default('company')`

### Issue: "Field types not recognized"
**Solution:** Odoo field types don't exist in Frappe. Use Frappe field types:
- `fields.Char` → `frappe.model.fields.Data`
- `fields.Integer` → `frappe.model.fields.Int`
- `fields.Many2one` → `frappe.model.fields.Link`
- etc.

### Issue: "Webhook endpoint not accessible"
**Solution:** Frappe whitelist methods don't create URL routes automatically. Use proper endpoint:
```
/api/method/finapify_payments.controllers.main.finapify_callback
```

## Success Indicators

✅ All Python files import only from `frappe`  
✅ No `models.Model` or `models.TransientModel` references  
✅ All database operations use Frappe API  
✅ Webhooks respond with `@frappe.whitelist()`  
✅ `hooks.py` properly configured  
✅ Module installs without errors  
✅ Doctypes appear in ERPNext UI  
✅ Callbacks process successfully  

## References

- [Frappe Framework Documentation](https://frappeframework.com/docs)
- [ERPNext Developer Documentation](https://docs.erpnext.com/docs/en/development)
- [Frappe Doctype Documentation](https://frappeframework.com/docs/user/en/introduction/1-architecture)
- [Finapify API Documentation](https://docs.finapify.com)

---

**Version:** 1.0  
**Last Updated:** May 7, 2026
