# Finapify Payments - ERPNext Module Setup Guide

This guide will help you properly deploy the Finapify Payments module in your ERPNext/Frappe environment.

## Prerequisites

- ERPNext v16 or later
- Frappe Framework v16 or later
- Python 3.10+
- MariaDB or PostgreSQL

## Installation Steps

### 1. Clone/Copy Module to Apps Directory

```bash
# If using Docker with Frappe Bench
cd ~/frappe-bench/apps
git clone <repo-url> finapify_payments

# Or if using local development
cp -r /path/to/finapify_payments ~/frappe-bench/apps/
```

### 2. Install Module

```bash
# Within the Frappe Bench environment
cd ~/frappe-bench

# For development setup
bench install-app finapify_payments

# For production setup
bench --site site1.local install-app finapify_payments
```

### 3. Create Doctypes

After installation, create the following doctypes through the ERPNext web UI or by running:

```bash
bench execute finapify_payments.setup.create_doctypes
```

### Required Doctypes

1. **Finapify Connection** - Stores Finapify API connection details
2. **Finapify Payment Request** - Individual payment request records
3. **Finapify Payment Batch** - Batch payment requests
4. **Finapify Log** - Audit logs for all transactions
5. **Finapify Settings** - Module configuration
6. **Finapify Bank Statement** - Bank statement imports
7. **Finapify Vendor Bank Map** - Vendor-to-bank mapping
8. **Finapify Journal Map** - Journal mapping configuration

### 4. Configure Module

1. Go to **Setup > Finapify Settings**
2. Enter your Finapify API credentials:
   - API Key
   - API Secret
   - API Base URL (default: https://api.finapify.com/webhook/erpnext)
   - n8n Webhook URL
3. Click "Test Authentication"

### 5. Setup Webhooks

Configure the following webhook endpoint in your Finapify/n8n dashboard:

```
Webhook URL: https://your-erpnext-url/api/method/finapify_payments.controllers.main.finapify_callback
Method: POST
Headers:
  - X-Finapify-Signature: (provided by Finapify)
  - Content-Type: application/json
```

## Fixing Common Errors

### Error: "No module named 'frappe_whatsapp', 'hrms', 'canarabank'"

If you see these errors in your Docker logs:

**Solution 1: Remove unused apps from sites/apps.txt**

```bash
# In your Frappe Docker environment
cd ~/frappe-bench/sites
# Edit apps.txt and remove lines for unused apps:
# Remove: frappe_whatsapp, hrms, canarabank if not needed

# Then restart:
docker restart <container-name>
```

**Solution 2: Completely remove unused apps**

```bash
cd ~/frappe-bench/apps
rm -rf frappe_whatsapp hrms canarabank
```

### Error: "Can't connect to MySQL server"

This indicates MariaDB container is not running or not accessible.

```bash
# Check if MariaDB container is running
docker ps | grep mariadb

# If not running, start it
docker start erpnext-one-database-1

# Or restart both containers
docker restart erpnext-one-database-1 erpnext-one-backend-1
```

### Error: "Module import failed with Odoo imports"

If you see Odoo-specific import errors, ensure you're using the Frappe-compatible version of the code:

```bash
# Verify all imports are Frappe (not Odoo)
grep -r "from odoo import" ~/frappe-bench/apps/finapify_payments/

# Should return nothing. If it does, the conversion isn't complete.
```

## Module Features

### Payment Request Management
- Create and manage individual payment requests
- Support for OTP-based authentication
- Automatic payment reconciliation
- Retry mechanism for failed payments

### Batch Payments
- Process multiple vendor bills in one batch
- Support for single-bank and multi-bank modes
- Partial success handling

### Bank Account Management
- Connect multiple bank accounts
- Vendor-to-bank mapping
- Automatic journal mapping

### Audit & Logging
- Complete audit trail of all transactions
- Payment status tracking
- Error logging and debugging

## API Endpoints

All endpoints require authentication and return JSON responses.

### Callback Endpoint
```
POST /api/method/finapify_payments.controllers.main.finapify_callback
```

Handles n8n webhook callbacks for payment status updates.

**Request Headers:**
```
X-Finapify-Signature: <HMAC-SHA256>
Content-Type: application/json
```

**Request Body:**
```json
{
  "n8n_request_id": "uuid",
  "correlation_id": "uuid",
  "status": "success|failed|part_success",
  "results": []
}
```

## Troubleshooting

### Module Not Loading

1. Check logs:
```bash
bench --site site1.local tail -f
```

2. Ensure all Python files use Frappe imports, not Odoo imports

3. Rebuild:
```bash
bench --site site1.local clear-cache
bench --site site1.local migrate
```

### Database Issues

1. Check database connection:
```bash
bench --site site1.local mariadb
```

2. If connection refused, restart MariaDB:
```bash
docker restart erpnext-one-database-1
```

### Missing Permissions

Grant user permissions to Finapify doctypes:

1. Go to **Setup > User and Permissions > User**
2. Select the user
3. Add roles: System Manager or create custom role with Finapify module permissions

## Development

For local development:

```bash
cd ~/frappe-bench

# Make changes to the code
# vim apps/finapify_payments/models/...

# Test your changes
bench --site site1.local execute finapify_payments.setup.test_setup

# Clear cache and restart
bench --site site1.local clear-cache
```

## Support

For issues or questions:
- Email: developer@finapify.com
- Documentation: https://docs.finapify.com

## License

LGPL-3.0
