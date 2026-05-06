import base64
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime

import frappe
from frappe import _

_logger = logging.getLogger(__name__)


def now_utc_str():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def generate_uuid():
    return str(uuid.uuid4())


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def safe_json_dumps(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"_error": "Failed to serialize"})


def mask_secrets(payload: dict) -> dict:
    def _mask(v):
        if not v:
            return v
        s = str(v)
        if len(s) <= 6:
            return "***"
        return s[:2] + "***" + s[-2:]

    if not isinstance(payload, dict):
        return payload
    out = json.loads(json.dumps(payload, default=str))

    for k in ["Authorization", "supabase_jwt", "jwt", "token", "otp", "otp_value", "value"]:
        if k in out:
            out[k] = "***"

    if "otp" in out and isinstance(out["otp"], dict):
        if "value" in out["otp"]:
            out["otp"]["value"] = "***"

    return out


def _derive_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode('utf-8')).digest()


def encrypt_text(plaintext: str, secret: str) -> str:
    if plaintext is None:
        return ""
    try:
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(_derive_key(secret))
        f = Fernet(key)
        return f.encrypt(plaintext.encode('utf-8')).decode('utf-8')
    except Exception:
        key = _derive_key(secret)
        data = plaintext.encode('utf-8')
        x = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
        return base64.b64encode(x).decode('utf-8')


def decrypt_text(ciphertext: str, secret: str) -> str:
    if not ciphertext:
        return ""
    try:
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(_derive_key(secret))
        f = Fernet(key)
        return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
    except Exception:
        try:
            raw = base64.b64decode(ciphertext.encode('utf-8'))
        except Exception:
            return ""
        key = _derive_key(secret)
        x = bytes([b ^ key[i % len(key)] for i, b in enumerate(raw)])
        return x.decode('utf-8', errors='ignore')


def hmac_sha256_hex(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()


def ensure_requests_available():
    try:
        import requests  # noqa
    except Exception as e:
        frappe.throw(_("Python 'requests' library is required. Error: %s") % str(e))


def http_post_json(url: str, headers: dict, payload: dict, timeout_s: int = 30):
    ensure_requests_available()
    import requests
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
    try:
        data = resp.json()
    except Exception:
        data = {"_raw": resp.text}
    return resp.status_code, data


def check_finapify_authenticated():
    """Raises frappe.ValidationError if Finapify API is not authenticated."""
    try:
        is_authenticated = frappe.db.get_single_value('Finapify Settings', 'is_authenticated')
    except Exception:
        is_authenticated = False

    if not is_authenticated:
        try:
            api_key = frappe.db.get_single_value('Finapify Settings', 'api_key')
            api_secret = frappe.db.get_single_value('Finapify Settings', 'api_secret')
        except Exception:
            api_key = None
            api_secret = None

        if not api_key or not api_secret:
            frappe.throw(
                _('Finapify API credentials are not configured. '
                  'Please set API Key and Secret in Finapify Settings and test authentication.')
            )
        else:
            frappe.throw(
                _('Finapify API is not authenticated. '
                  'Please verify your API credentials and click "Test Authentication" in Finapify Settings.')
            )

    return True


def get_finapify_auth_status():
    try:
        return {
            'is_authenticated': frappe.db.get_single_value('Finapify Settings', 'is_authenticated') or False,
            'api_key': frappe.db.get_single_value('Finapify Settings', 'api_key') or '',
            'api_url': frappe.db.get_single_value('Finapify Settings', 'api_url') or 'https://api.finapify.com/webhook/erpnext',
            'last_auth_at': frappe.db.get_single_value('Finapify Settings', 'last_auth_at') or '',
            'auth_error': frappe.db.get_single_value('Finapify Settings', 'auth_error') or '',
        }
    except Exception as e:
        _logger.error("Error getting Finapify auth status: %s", str(e))
        return {
            'is_authenticated': False,
            'api_key': '',
            'api_url': 'https://api.finapify.com/webhook/erpnext',
            'last_auth_at': '',
            'auth_error': str(e),
        }
