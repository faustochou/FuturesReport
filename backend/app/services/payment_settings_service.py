"""
Payment gateway settings service.

Single source of truth for reading/writing payment-related configuration
(gateway keys, webhook secrets, ...). Mirrors the "DB overrides env" pattern
used by shineyang's lib/payment/gateway-factory.ts:

    1. site_settings table (admin-editable, encrypted for secrets)
    2. os.environ fallback (Zeabur / .env deployment)

Sensitive values (Stripe secret key, webhook secret) are encrypted at rest
with a Fernet key derived from Config.SECRET_KEY. Nothing in this module
ever returns encrypted ciphertext or logs plaintext; callers outside this
module should only ever see masked hints via mask()/get_effective_settings().
"""

import base64
import hashlib
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from ..config import Config
from ..db.database import get_db
from ..db.models import SiteSettings
from ..utils.logger import get_logger

logger = get_logger("futuresreport.payment_settings")


# ---------------------------------------------------------------------------
# Setting keys
# ---------------------------------------------------------------------------

GATEWAY = "payment.gateway"

STRIPE_SECRET_KEY = "payment.stripe.secret_key"
STRIPE_WEBHOOK_SECRET = "payment.stripe.webhook_secret"
STRIPE_PUBLISHABLE_KEY = "payment.stripe.publishable_key"

# Reserved for future gateways — interfaces only, not wired up yet.
PAYUNI_MERCHANT_ID = "payment.payuni.merchant_id"
PAYUNI_HASH_KEY = "payment.payuni.hash_key"
PAYUNI_HASH_IV = "payment.payuni.hash_iv"
SHOPLINE_API_KEY = "payment.shopline.api_key"
SHOPLINE_API_SECRET = "payment.shopline.api_secret"

DEFAULT_GATEWAY = "stripe"

# DB key -> env var fallback name
_ENV_FALLBACK: Dict[str, str] = {
    GATEWAY: "PAYMENT_GATEWAY",
    STRIPE_SECRET_KEY: "STRIPE_SECRET_KEY",
    STRIPE_WEBHOOK_SECRET: "STRIPE_WEBHOOK_SECRET",
    STRIPE_PUBLISHABLE_KEY: "STRIPE_PUBLISHABLE_KEY",
    PAYUNI_MERCHANT_ID: "PAYUNI_MERCHANT_ID",
    PAYUNI_HASH_KEY: "PAYUNI_HASH_KEY",
    PAYUNI_HASH_IV: "PAYUNI_HASH_IV",
    SHOPLINE_API_KEY: "SHOPLINE_API_KEY",
    SHOPLINE_API_SECRET: "SHOPLINE_API_SECRET",
}

# Keys whose DB value must be encrypted at rest.
_ENCRYPTED_KEYS = frozenset({
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
    PAYUNI_HASH_KEY,
    PAYUNI_HASH_IV,
    SHOPLINE_API_SECRET,
})


# ---------------------------------------------------------------------------
# Encryption — Fernet key derived from the Flask SECRET_KEY
# ---------------------------------------------------------------------------

def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet() -> Fernet:
    return Fernet(_derive_fernet_key(Config.SECRET_KEY))


def _encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(token: str) -> Optional[str]:
    try:
        return _get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.error("[PaymentSettings] 設定解密失敗，SECRET_KEY 可能已變更")
        return None


# ---------------------------------------------------------------------------
# Read / write
# ---------------------------------------------------------------------------

def get_setting_with_source(key: str) -> Tuple[Optional[str], str]:
    """Return (value, source). source is one of "db" / "env" / "none"."""
    with get_db() as db:
        row = db.execute(
            select(SiteSettings).where(SiteSettings.key == key)
        ).scalar_one_or_none()
        if row and row.value:
            value = row.value
            if key in _ENCRYPTED_KEYS:
                value = _decrypt(value)
            if value:
                return value, "db"

    env_var = _ENV_FALLBACK.get(key)
    if env_var:
        value = os.environ.get(env_var, "").strip()
        if value:
            return value, "env"

    return None, "none"


def get_setting(key: str) -> Optional[str]:
    value, _source = get_setting_with_source(key)
    return value


def set_setting(key: str, value: Optional[str]) -> None:
    """Write a setting to the DB. Empty/None deletes the row (falls back to env)."""
    value = (value or "").strip()
    with get_db() as db:
        row = db.execute(
            select(SiteSettings).where(SiteSettings.key == key)
        ).scalar_one_or_none()

        if not value:
            if row is not None:
                db.delete(row)
            return

        stored = _encrypt(value) if key in _ENCRYPTED_KEYS else value
        now = datetime.utcnow()
        if row is not None:
            row.value = stored
            row.updated_at = now
        else:
            db.add(SiteSettings(key=key, value=stored, updated_at=now))


# ---------------------------------------------------------------------------
# Convenience accessors
# ---------------------------------------------------------------------------

def get_active_gateway_type() -> str:
    return get_setting(GATEWAY) or DEFAULT_GATEWAY


def get_stripe_secret_key() -> Optional[str]:
    return get_setting(STRIPE_SECRET_KEY)


def get_stripe_webhook_secret() -> Optional[str]:
    return get_setting(STRIPE_WEBHOOK_SECRET)


def get_stripe_publishable_key() -> Optional[str]:
    return get_setting(STRIPE_PUBLISHABLE_KEY)


def is_stripe_configured() -> bool:
    return bool(get_stripe_secret_key()) and bool(get_stripe_webhook_secret())


# ---------------------------------------------------------------------------
# Admin UI helpers — never expose plaintext secrets
# ---------------------------------------------------------------------------

def mask(value: Optional[str]) -> Optional[str]:
    """Mask a secret for display, e.g. sk_test_...ab12. Never returns plaintext."""
    if not value:
        return None
    if len(value) <= 11:
        return f"{value[:2]}...{value[-2:]}"
    return f"{value[:7]}...{value[-4:]}"


def get_effective_settings() -> Dict[str, Dict[str, Any]]:
    """Per-key masked snapshot (configured?, source, hint) for the admin UI.

    Values are never returned in plaintext — callers must not add a
    "raw"/"value" field here.
    """
    keys = (GATEWAY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PUBLISHABLE_KEY)
    result: Dict[str, Dict[str, Any]] = {}
    for key in keys:
        value, source = get_setting_with_source(key)
        result[key] = {
            "configured": bool(value),
            "source": source,
            "hint": value if key == GATEWAY else mask(value),
        }
    return result
