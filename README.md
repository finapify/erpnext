# Finapify Payments for ERPNext

Production-ready integration to initiate vendor payments from ERPNext using Finapify (Supabase + n8n).

## Key Features

✅ **Connect Finapify** - Secure JWT authentication with Supabase  
✅ **Single & Bulk Payments** - Pay vendor bills individually or in batches  
✅ **OTP Authentication** - Secure payment authorization with OTP  
✅ **Async Callbacks** - HMAC-verified webhook callbacks from n8n  
✅ **Idempotency** - Built-in duplicate prevention  
✅ **Retry Mechanism** - Automatic retry with exponential backoff  
✅ **Auto-Reconciliation** - Automatically creates account payments and reconciles bills  
✅ **Audit Logs** - Complete transaction history and debugging  
✅ **Journal Mapping** - Map Finapify bank accounts to ERPNext journals  
✅ **Vendor Bank Mapping** - Manage vendor bank account details  

## Compatibility

- **ERPNext**: v16.0+
- **Frappe Framework**: v16.0+
- **Python**: 3.10+
- **Database**: MariaDB 10.5+ or PostgreSQL 12+

## Installation

See [INSTALLATION.md](INSTALLATION.md) for detailed setup instructions.

### Quick Start

```bash
# Clone the repository to your Frappe Bench apps directory
cd ~/frappe-bench/apps
git clone <repository-url> finapify_payments

# Install the app
cd ~/frappe-bench
bench --site <site-name> install-app finapify_payments

# Migrate and setup
bench --site <site-name> migrate
bench --site <site-name> execute finapify_payments.setup.after_install
```

## Configuration

1. **Go to Finapify Settings**
   - Navigate to Setup > Finapify Settings
   - Enter your Finapify API credentials
   - Configure n8n webhook URL
   - Test connection

2. **Setup Bank Mappings**
   - Create vendor bank account mappings
   - Map Finapify bank accounts to ERPNext journals

3. **Configure Webhooks**
   - Add Finapify callback endpoint to your n8n webhook
   - Verify HMAC signature verification is enabled

## Usage

### Making a Single Payment

1. Create or select a vendor bill
2. Click "Pay via Finapify"
3. Select source bank account
4. Enter vendor bank details
5. Confirm payment and enter OTP when prompted
6. System automatically creates and reconciles the payment

### Processing Batch Payments

1. Go to Finapify > Payment Batch
2. Create new batch
3. Add vendor bills
4. Select source bank (for single-bank mode)
5. Submit batch
6. Enter OTP when prompted
7. System processes all payments asynchronously

### Monitoring

- **Finapify Dashboard** - View payment statistics and status
- **Payment Log** - Complete audit trail of all transactions
- **Transaction Details** - View request/response payloads for debugging

## Architecture

```
ERPNext (Frappe)
    ↓
    ├─ Payment Request/Batch
    │   └─ Calls n8n webhook
    │
    └─ Callback Handler
        └─ Receives async updates from n8n
            └─ Creates/updates Account Payments
            └─ Reconciles to vendor bills
```

## API Endpoints

### Finapify Callback
```
POST /api/method/finapify_payments.controllers.main.finapify_callback
```

Webhook endpoint for receiving payment status updates from n8n.

**Headers:**
- `X-Finapify-Signature`: HMAC-SHA256 signature for verification
- `Content-Type`: application/json

**Request Body:**
```json
{
  "n8n_request_id": "uuid",
  "correlation_id": "uuid",
  "status": "success|failed|part_success",
  "results": [...]
}
```

## Database Schema

### Main Doctypes

- **Finapify Connection** - API connection settings and JWT storage
- **Finapify Payment Request** - Individual payment request tracking
- **Finapify Payment Batch** - Batch payment management
- **Finapify Log** - Audit trail and debugging logs
- **Finapify Settings** - Module configuration
- **Finapify Vendor Bank Map** - Vendor banking details
- **Finapify Journal Map** - Journal mapping configuration

## Error Handling

The module includes comprehensive error handling:

- **Validation Errors** - Caught and returned as user-friendly messages
- **API Errors** - Logged with full request/response details
- **Database Errors** - Automatic retry with logging
- **Signature Verification** - Cryptographic verification of all callbacks

## Security

🔒 **JWT Encryption** - Supabase JWTs stored encrypted in database  
🔒 **HMAC Verification** - All callbacks verified with HMAC-SHA256  
🔒 **Audit Logging** - Complete log of all API calls and state changes  
🔒 **Permission Control** - Fine-grained role-based access control  
🔒 **Secret Management** - Secure callback secret generation and storage  

## Troubleshooting

### Common Issues

**Module not loading after installation**
- Check that all Python imports use Frappe (not Odoo)
- Clear cache: `bench --site <site> clear-cache`
- Restart Frappe server

**Database connection errors**
- Verify MariaDB/PostgreSQL is running
- Check database credentials in site_config.json
- Restart database container if using Docker

**Webhook signature verification failures**
- Ensure callback secret matches in both ERPNext and Finapify
- Verify HMAC-SHA256 algorithm is used
- Check request body isn't modified after signing

**Payment stuck in "otp_pending"**
- User may have missed OTP prompt
- Check system logs for OTP errors
- Try canceling and retrying the payment

For more help, see [INSTALLATION.md](INSTALLATION.md) troubleshooting section.

## Development

### Project Structure

This is a standard Frappe app: the repo root holds packaging files, and the
importable Python package lives one level down in `finapify_payments/`.

```
finapify_payments/                  (repo root — bench clones this into apps/)
├── setup.py (Python packaging — pip/setuptools)
├── requirements.txt
└── finapify_payments/              (the actual app package Frappe imports)
    ├── __init__.py
    ├── hooks.py (Frappe configuration)
    ├── modules.txt (registers the "Finapify Payments" module)
    ├── setup.py (after_install hook, test_finapify_connection)
    ├── models/
    │   ├── __init__.py
    │   ├── utils.py (Helper functions)
    │   ├── finapify_connection.py
    │   ├── finapify_payment_request.py
    │   ├── finapify_payment_batch.py
    │   ├── finapify_log.py
    │   ├── purchase_invoice_override.py (Purchase Invoice override)
    │   ├── purchase_order_override.py (Purchase Order override)
    │   ├── supplier_override.py (Supplier override)
    │   └── ...other models
    ├── controllers/
    │   ├── __init__.py
    │   └── main.py (webhook callback + whitelisted API methods)
    ├── wizards/
    │   ├── __init__.py
    │   ├── finapify_connect_wizard.py
    │   └── ...other wizards
    ├── public/js/
    │   ├── purchase_invoice.js ("Pay with Finapify" button)
    │   └── purchase_invoice_list.js (bulk "Pay with Finapify" list action)
    ├── fixtures/
    │   └── module_def.json
    └── finapify_payments/           (the "Finapify Payments" module — Frappe
                                       needs this extra nesting level since the
                                       module name matches the app name)
        ├── doctype/
        │   └── <doctype_name>/<doctype_name>.json + .py + .js  (one folder per DocType)
        └── workspace/
            └── finapify_payments/finapify_payments.json
```

### Running Tests

```bash
# Execute a setup sanity check
bench --site <site> execute finapify_payments.setup.test_finapify_connection

# View logs
bench --site <site> tail -f
```
The whitelisted document methods (`action_finapify_pay`,
`action_submit_to_n8n`, etc.) and API endpoints are fully wired up
server-side and can be called directly via `frappe.call`/REST today; adding
the corresponding buttons/pages is tracked as follow-up UI work.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

- **Email**: developer@finapify.com
- **Documentation**: https://docs.finapify.com
- **GitHub Issues**: Report bugs via GitHub issues

## License

This project is licensed under the LGPL-3.0 License.

## Changelog

### v0.1.0
- Pure Frappe/ERPNext implementation (no Odoo dependencies)
- Full support for single and batch payments
- HMAC callback verification
- Auto-reconciliation
- Complete audit logging

---

**Made with ❤️ by Finapify**
