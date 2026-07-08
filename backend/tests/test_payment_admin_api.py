"""
Tests for the admin payment settings API (Phase 4):
  GET  /api/admin/payment/settings
  PUT  /api/admin/payment/settings
  POST /api/admin/payment/test-connection

Monkeypatches the Stripe SDK so no network calls are made.

Run from backend/ directory:
    pytest tests/test_payment_admin_api.py -v
"""

import os
import tempfile
import types

import pytest
import stripe

_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="futuresreport_payadmin_")
os.close(_db_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-for-payment-admin-api"
os.environ["FLASK_DEBUG"] = "False"


class FakeBalance:
    def retrieve(self, params=None, options=None):
        return types.SimpleNamespace(available=[types.SimpleNamespace(currency="twd")])


class FakeV1:
    def __init__(self):
        self.balance = FakeBalance()


class FakeStripeClient:
    def __init__(self, secret_key):
        self.secret_key = secret_key
        self.v1 = FakeV1()


@pytest.fixture(scope="module")
def app():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
    os.environ["SECRET_KEY"] = "test-secret-key-for-payment-admin-api"
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    yield application
    try:
        os.unlink(_db_path)
    except OSError:
        pass


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def admin_token(client):
    resp = client.post("/api/auth/register", json={
        "username": "payadmin_test_admin",
        "password": "payadminpass123",
    })
    assert resp.status_code == 201
    return resp.get_json()["data"]["token"]


@pytest.fixture(autouse=True)
def _patch_stripe_sdk(monkeypatch):
    monkeypatch.setattr(stripe, "StripeClient", FakeStripeClient)


@pytest.fixture(autouse=True)
def _clear_payment_settings(app):
    from app.services import payment_settings_service as pay_settings

    def _reset():
        with app.app_context():
            for key in (
                pay_settings.GATEWAY,
                pay_settings.STRIPE_SECRET_KEY,
                pay_settings.STRIPE_WEBHOOK_SECRET,
                pay_settings.STRIPE_PUBLISHABLE_KEY,
            ):
                pay_settings.set_setting(key, None)

    _reset()
    yield
    _reset()


def _auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------------------------------------------------------------------------
# GET /api/admin/payment/settings
# ---------------------------------------------------------------------------

def test_get_payment_settings_defaults(app, client, admin_token):
    resp = client.get("/api/admin/payment/settings", headers=_auth(admin_token))
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["gateway"] == "stripe"
    assert data["stripe"]["secret_key"]["configured"] is False
    assert data["stripe"]["secret_key"]["source"] == "none"
    assert data["is_test_mode"] is False
    assert data["webhook_url"].endswith("/api/subscription/webhook")


def test_get_payment_settings_never_leaks_plaintext(app, client, admin_token):
    resp = client.put(
        "/api/admin/payment/settings",
        json={"stripe_secret_key": "sk_test_super_secret_value_123"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200

    resp = client.get("/api/admin/payment/settings", headers=_auth(admin_token))
    body = resp.get_json()
    assert "sk_test_super_secret_value_123" not in str(body)

    entry = body["data"]["stripe"]["secret_key"]
    assert entry["configured"] is True
    assert entry["source"] == "db"
    assert entry["hint"].startswith("sk_test")
    assert entry["hint"] != "sk_test_super_secret_value_123"


# ---------------------------------------------------------------------------
# PUT /api/admin/payment/settings
# ---------------------------------------------------------------------------

def test_put_payment_settings_updates_and_clears(app, client, admin_token):
    resp = client.put(
        "/api/admin/payment/settings",
        json={
            "stripe_secret_key": "sk_test_abc123",
            "stripe_webhook_secret": "whsec_abc123",
            "stripe_publishable_key": "pk_test_abc123",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200

    with app.app_context():
        from app.services import payment_settings_service as pay_settings
        assert pay_settings.get_stripe_secret_key() == "sk_test_abc123"
        assert pay_settings.get_stripe_webhook_secret() == "whsec_abc123"
        assert pay_settings.get_stripe_publishable_key() == "pk_test_abc123"

    # Empty string clears the DB override
    resp = client.put(
        "/api/admin/payment/settings",
        json={"stripe_secret_key": ""},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    with app.app_context():
        from app.services import payment_settings_service as pay_settings
        assert pay_settings.get_stripe_secret_key() is None


def test_put_payment_settings_rejects_reserved_gateway(app, client, admin_token):
    resp = client.put(
        "/api/admin/payment/settings",
        json={"gateway": "payuni"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400
    assert "尚未支援" in resp.get_json()["error"]


def test_put_payment_settings_rejects_unknown_gateway(app, client, admin_token):
    resp = client.put(
        "/api/admin/payment/settings",
        json={"gateway": "paypal"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 400
    assert "未知的金流閘道" in resp.get_json()["error"]


def test_put_payment_settings_accepts_stripe_gateway(app, client, admin_token):
    resp = client.put(
        "/api/admin/payment/settings",
        json={"gateway": "stripe"},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    with app.app_context():
        from app.services import payment_settings_service as pay_settings
        assert pay_settings.get_active_gateway_type() == "stripe"


# ---------------------------------------------------------------------------
# POST /api/admin/payment/test-connection
# ---------------------------------------------------------------------------

def test_test_connection_without_secret_key_returns_400(app, client, admin_token):
    resp = client.post("/api/admin/payment/test-connection", headers=_auth(admin_token))
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_test_connection_success(app, client, admin_token):
    client.put(
        "/api/admin/payment/settings",
        json={"stripe_secret_key": "sk_test_conn_123"},
        headers=_auth(admin_token),
    )
    resp = client.post("/api/admin/payment/test-connection", headers=_auth(admin_token))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["success"] is True
    assert "TWD" in body["data"]["message"]
