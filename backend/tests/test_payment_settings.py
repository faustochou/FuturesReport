"""
Unit tests for payment_settings_service — DB-first / env-fallback config
with encrypted secrets. Runs against a temp SQLite DB.

Run from backend/ directory:
    pytest tests/test_payment_settings.py -v
"""

import os
import tempfile

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="futuresreport_payment_")
os.close(_db_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-for-payment-settings"
os.environ["FLASK_DEBUG"] = "False"


@pytest.fixture(scope="module")
def app():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # Re-assert (other test modules mutate these same process-global env vars
    # at import time, so the values seen here at fixture-setup time may have
    # been overwritten by whichever module was collected last).
    os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
    os.environ["SECRET_KEY"] = "test-secret-key-for-payment-settings"
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    yield application
    try:
        os.unlink(_db_path)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _app_context(app):
    with app.app_context():
        yield


@pytest.fixture(autouse=True)
def _clear_settings():
    """Wipe payment.* rows and relevant env vars before/after each test."""
    from app.services import payment_settings_service as pay_settings

    def _reset():
        for key in (
            pay_settings.GATEWAY,
            pay_settings.STRIPE_SECRET_KEY,
            pay_settings.STRIPE_WEBHOOK_SECRET,
            pay_settings.STRIPE_PUBLISHABLE_KEY,
        ):
            pay_settings.set_setting(key, None)
        for env_var in (
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "STRIPE_PUBLISHABLE_KEY",
            "PAYMENT_GATEWAY",
        ):
            os.environ.pop(env_var, None)

    _reset()
    yield
    _reset()


# ---------------------------------------------------------------------------
# DB priority / env fallback
# ---------------------------------------------------------------------------

def test_env_fallback_when_db_empty():
    from app.services import payment_settings_service as pay_settings

    os.environ["STRIPE_SECRET_KEY"] = "sk_test_env_value"
    value, source = pay_settings.get_setting_with_source(pay_settings.STRIPE_SECRET_KEY)
    assert value == "sk_test_env_value"
    assert source == "env"


def test_db_value_overrides_env():
    from app.services import payment_settings_service as pay_settings

    os.environ["STRIPE_SECRET_KEY"] = "sk_test_env_value"
    pay_settings.set_setting(pay_settings.STRIPE_SECRET_KEY, "sk_test_db_value")

    value, source = pay_settings.get_setting_with_source(pay_settings.STRIPE_SECRET_KEY)
    assert value == "sk_test_db_value"
    assert source == "db"


def test_no_value_anywhere_returns_none_source():
    from app.services import payment_settings_service as pay_settings

    value, source = pay_settings.get_setting_with_source(pay_settings.STRIPE_SECRET_KEY)
    assert value is None
    assert source == "none"


def test_clearing_db_value_falls_back_to_env():
    from app.services import payment_settings_service as pay_settings

    os.environ["STRIPE_SECRET_KEY"] = "sk_test_env_value"
    pay_settings.set_setting(pay_settings.STRIPE_SECRET_KEY, "sk_test_db_value")
    pay_settings.set_setting(pay_settings.STRIPE_SECRET_KEY, "")  # empty string clears

    value, source = pay_settings.get_setting_with_source(pay_settings.STRIPE_SECRET_KEY)
    assert value == "sk_test_env_value"
    assert source == "env"


def test_default_gateway_is_stripe():
    from app.services import payment_settings_service as pay_settings

    assert pay_settings.get_active_gateway_type() == "stripe"


# ---------------------------------------------------------------------------
# Encryption round trip
# ---------------------------------------------------------------------------

def test_encrypted_value_round_trips():
    from app.services import payment_settings_service as pay_settings
    from app.db.database import get_db
    from app.db.models import SiteSettings
    from sqlalchemy import select

    pay_settings.set_setting(pay_settings.STRIPE_SECRET_KEY, "sk_test_super_secret_123")

    with get_db() as db:
        row = db.execute(
            select(SiteSettings).where(SiteSettings.key == pay_settings.STRIPE_SECRET_KEY)
        ).scalar_one()
        # Ciphertext must not equal (or contain) the plaintext
        assert row.value != "sk_test_super_secret_123"
        assert "sk_test_super_secret_123" not in row.value

    assert pay_settings.get_stripe_secret_key() == "sk_test_super_secret_123"


def test_publishable_key_stored_in_plaintext():
    """Publishable key is public-facing (used by the frontend) — no need to encrypt."""
    from app.services import payment_settings_service as pay_settings
    from app.db.database import get_db
    from app.db.models import SiteSettings
    from sqlalchemy import select

    pay_settings.set_setting(pay_settings.STRIPE_PUBLISHABLE_KEY, "pk_test_visible_123")

    with get_db() as db:
        row = db.execute(
            select(SiteSettings).where(SiteSettings.key == pay_settings.STRIPE_PUBLISHABLE_KEY)
        ).scalar_one()
        assert row.value == "pk_test_visible_123"


# ---------------------------------------------------------------------------
# Masking never leaks plaintext
# ---------------------------------------------------------------------------

def test_mask_does_not_leak_plaintext():
    from app.services import payment_settings_service as pay_settings

    secret = "sk_test_ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    masked = pay_settings.mask(secret)
    assert masked != secret
    assert secret not in masked
    assert masked.startswith("sk_test")
    assert masked.endswith(secret[-4:])


def test_mask_none_returns_none():
    from app.services import payment_settings_service as pay_settings

    assert pay_settings.mask(None) is None
    assert pay_settings.mask("") is None


def test_effective_settings_never_exposes_raw_value():
    from app.services import payment_settings_service as pay_settings

    pay_settings.set_setting(pay_settings.STRIPE_SECRET_KEY, "sk_test_super_secret_123")
    snapshot = pay_settings.get_effective_settings()

    entry = snapshot[pay_settings.STRIPE_SECRET_KEY]
    assert entry["configured"] is True
    assert entry["source"] == "db"
    assert "sk_test_super_secret_123" not in str(entry)
    assert set(entry.keys()) == {"configured", "source", "hint"}


# ---------------------------------------------------------------------------
# is_stripe_configured requires both secret + webhook secret
# ---------------------------------------------------------------------------

def test_is_stripe_configured_requires_both_keys():
    from app.services import payment_settings_service as pay_settings

    assert pay_settings.is_stripe_configured() is False

    pay_settings.set_setting(pay_settings.STRIPE_SECRET_KEY, "sk_test_x")
    assert pay_settings.is_stripe_configured() is False

    pay_settings.set_setting(pay_settings.STRIPE_WEBHOOK_SECRET, "whsec_x")
    assert pay_settings.is_stripe_configured() is True
