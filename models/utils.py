import base64
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from datetime import datetime

from odoo import _
from odoo.exceptions import UserError

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
    """Return a copy with common sensitive fields masked."""
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

    # mask common keys
    for k in ["Authorization", "supabase_jwt", "jwt", "token", "otp", "otp_value", "value"]:
        if k in out:
            out[k] = "***"

    # nested masking
    if "otp" in out and isinstance(out["otp"], dict):
        if "value" in out["otp"]:
            out["otp"]["value"] = "***"

    return out


# --------------------------
# Encryption helpers
# --------------------------
# We prefer Fernet if 'cryptography' is available.
# If not, we fallback to a deterministic XOR stream derived from secret.
# NOTE: XOR fallback is not strong crypto; keep callback_secret private and rotate.


def _derive_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode('utf-8')).digest()


def encrypt_text(plaintext: str, secret: str) -> str:
    if plaintext is None:
        return ""

    # Fernet if available
    try:
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(_derive_key(secret))
        f = Fernet(key)
        token = f.encrypt(plaintext.encode('utf-8'))
        return token.decode('utf-8')
    except Exception:
        # XOR fallback
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
        data = f.decrypt(ciphertext.encode('utf-8'))
        return data.decode('utf-8')
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
        raise UserError(_("Python 'requests' library is required. Error: %s") % str(e))


def http_post_json(url: str, headers: dict, payload: dict, timeout_s: int = 30):
    ensure_requests_available()
    import requests

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
    try:
        data = resp.json()
    except Exception:
        data = {"_raw": resp.text}
    return resp.status_code, data


def check_finapify_authenticated(env):
    """
    Check if Finapify API is authenticated.
    Raises UserError if not authenticated.
    Returns True if authenticated.
    """
    icp = env['ir.config_parameter'].sudo()
    is_authenticated = icp.get_param('finapify_payments.is_authenticated', default='False') == 'True'
    
    if not is_authenticated:
        api_key = icp.get_param('finapify_payments.api_key', default='')
        api_secret = icp.get_param('finapify_payments.api_secret', default='')
        
        if not api_key or not api_secret:
            raise UserError(
                _('Finapify API credentials are not configured. '
                  'Please set API Key and Secret in Finapify Settings and test authentication.')
            )
        else:
            raise UserError(
                _('Finapify API is not authenticated. '
                  'Please verify your API credentials and click "Test Authentication" in Finapify Settings.')
            )
    
    return True


def get_finapify_auth_status(env):
    """Get current Finapify authentication status"""
    icp = env['ir.config_parameter'].sudo()
    return {
        'is_authenticated': icp.get_param('finapify_payments.is_authenticated', default='False') == 'True',
        'api_key': icp.get_param('finapify_payments.api_key', default=''),
        'api_url': icp.get_param('finapify_payments.api_url', default='https://api.finapify.com/webhook/erpnext'),
        'last_auth_at': icp.get_param('finapify_payments.last_auth_at', default=''),
        'auth_error': icp.get_param('finapify_payments.auth_error', default=''),
    }
