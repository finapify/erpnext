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

```
finapify_payments/
├── __init__.py
├── __manifest__.py (for Odoo - deprecated)
├── hooks.py (Frappe configuration)
├── setup.py (Installation/setup hooks)
├── models/
│   ├── __init__.py
│   ├── utils.py (Helper functions)
│   ├── finapify_connection.py
│   ├── finapify_payment_request.py
│   ├── finapify_payment_batch.py
│   ├── finapify_log.py
│   ├── account_move_inherit.py
│   └── ...other models
├── controllers/
│   ├── __init__.py
│   └── main.py (Webhook handlers)
├── wizards/
│   ├── __init__.py
│   ├── finapify_connect_wizard.py
│   └── ...other wizards
├── views/
│   ├── ...XML view definitions
├── data/
│   ├── finapify_sequences.xml
│   └── finapify_cron.xml
└── INSTALLATION.md
```

### Running Tests

```bash
# Execute a setup test
bench --site <site> execute finapify_payments.setup.test_finapify_connection

# View logs
bench --site <site> tail -f
```

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

This project is licensed under the LGPL-3.0 License - see LICENSE file for details.

## Changelog

### v16.0.1.0.0 (2026-05-07)
- Initial release for ERPNext v16
- Converted from Odoo to Frappe framework
- Full support for single and batch payments
- HMAC callback verification
- Auto-reconciliation
- Complete audit logging

---

**Made with ❤️ by Finapify**
