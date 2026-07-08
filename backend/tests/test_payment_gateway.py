"""
Integration tests for the pluggable payment gateway layer (Phase 2).

Monkeypatches the Stripe SDK (stripe.StripeClient, stripe.Webhook.construct_event)
so no network calls are made. Verifies that checkout / portal / webhook behaviour
through subscription_service -> payment.factory -> StripeGateway matches what the
pre-refactor direct-Stripe-SDK code did.

Run from backend/ directory:
    pytest tests/test_payment_gateway.py -v
"""

import json
import os
import tempfile
import types

import pytest
import stripe

_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="futuresreport_paygw_")
os.close(_db_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-for-payment-gateway"
os.environ["FLASK_DEBUG"] = "False"

FIXED_PERIOD_END_TS = 1735689600  # 2025-01-01T00:00:00Z


# ---------------------------------------------------------------------------
# Fake Stripe SDK
# ---------------------------------------------------------------------------

class FakeCheckoutSessions:
    def __init__(self):
        self.calls = []

    def create(self, params):
        self.calls.append(params)
        return types.SimpleNamespace(url="https://checkout.stripe.com/fake-session", id="cs_fake_123")


class FakeBillingPortalSessions:
    def __init__(self):
        self.calls = []

    def create(self, params):
        self.calls.append(params)
        return types.SimpleNamespace(url="https://billing.stripe.com/fake-portal")


class FakeSubscriptions:
    def __init__(self):
        self.retrieve_calls = []
        self.cancel_calls = []

    def retrieve(self, sub_id, params=None, options=None):
        self.retrieve_calls.append(sub_id)
        return types.SimpleNamespace(current_period_end=FIXED_PERIOD_END_TS)

    def cancel(self, sub_id, params=None, options=None):
        self.cancel_calls.append(sub_id)
        return types.SimpleNamespace(id=sub_id, status="canceled")


class FakeRefunds:
    def __init__(self, should_fail=False):
        self.calls = []
        self.should_fail = should_fail

    def create(self, params=None, options=None):
        self.calls.append((params, options))
        if self.should_fail:
            raise stripe.StripeError("card_declined")
        return types.SimpleNamespace(id="re_fake_123")


class FakeBalance:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    def retrieve(self, params=None, options=None):
        if self.should_fail:
            raise stripe.StripeError("connection failed")
        return types.SimpleNamespace(
            available=[types.SimpleNamespace(currency="twd"), types.SimpleNamespace(currency="usd")]
        )


class FakeV1:
    def __init__(self):
        self.checkout = types.SimpleNamespace(sessions=FakeCheckoutSessions())
        self.billing_portal = types.SimpleNamespace(sessions=FakeBillingPortalSessions())
        self.subscriptions = FakeSubscriptions()
        self.refunds = FakeRefunds()
        self.balance = FakeBalance()


class FakeStripeClient:
    """Drop-in replacement for stripe.StripeClient — records calls, makes no network I/O."""
    last_instance = None

    def __init__(self, secret_key):
        self.secret_key = secret_key
        self.v1 = FakeV1()
        FakeStripeClient.last_instance = self


def fake_construct_event(payload, sig_header, secret):
    """Bypass real signature verification; just parse the JSON body."""
    if not secret:
        raise RuntimeError("no webhook secret configured for fake construct_event")
    return json.loads(payload)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
    os.environ["SECRET_KEY"] = "test-secret-key-for-payment-gateway"
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


@pytest.fixture(autouse=True)
def _patch_stripe_sdk(monkeypatch):
    monkeypatch.setattr(stripe, "StripeClient", FakeStripeClient)
    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(fake_construct_event))


@pytest.fixture(autouse=True)
def _configure_payment_settings(app):
    from app.services import payment_settings_service as pay_settings

    with app.app_context():
        pay_settings.set_setting(pay_settings.STRIPE_SECRET_KEY, "sk_test_fake_123")
        pay_settings.set_setting(pay_settings.STRIPE_WEBHOOK_SECRET, "whsec_fake_123")
        pay_settings.set_setting(pay_settings.STRIPE_PUBLISHABLE_KEY, "pk_test_fake_123")
        pay_settings.set_setting(pay_settings.GATEWAY, None)
    yield
    with app.app_context():
        pay_settings.set_setting(pay_settings.GATEWAY, None)


@pytest.fixture(scope="module")
def test_user(app, client):
    with app.app_context():
        from app.services import subscription_service as svc
        svc.update_tier("lite", is_available=True, stripe_price_id="price_fake_lite")

    resp = client.post("/api/auth/register", json={
        "username": "paygw_test_user",
        "password": "paygwpass123",
    })
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    return {"user_id": data["user"]["user_id"], "token": data["token"]}


# ---------------------------------------------------------------------------
# Checkout session — through factory -> StripeGateway
# ---------------------------------------------------------------------------

def test_create_checkout_session_uses_gateway(app, test_user):
    from app.services import subscription_service as svc

    with app.app_context():
        url = svc.create_checkout_session(
            user_id=test_user["user_id"],
            user_email="paygw_test_user",
            tier_code="lite",
            success_url="https://example.com/ok",
            cancel_url="https://example.com/cancel",
        )

    assert url == "https://checkout.stripe.com/fake-session"
    call = FakeStripeClient.last_instance.v1.checkout.sessions.calls[-1]
    assert call["line_items"][0]["price"] == "price_fake_lite"
    assert call["metadata"]["user_id"] == test_user["user_id"]
    assert call["metadata"]["tier_code"] == "lite"
    assert call["mode"] == "subscription"


def test_create_checkout_session_unknown_tier_raises_value_error(app, test_user):
    from app.services import subscription_service as svc

    with app.app_context():
        with pytest.raises(ValueError):
            svc.create_checkout_session(
                user_id=test_user["user_id"],
                user_email="x",
                tier_code="does_not_exist",
                success_url="https://example.com/ok",
                cancel_url="https://example.com/cancel",
            )


# ---------------------------------------------------------------------------
# Webhook — full route -> factory -> StripeGateway -> DB
# ---------------------------------------------------------------------------

def test_webhook_checkout_completed_activates_subscription(app, client, test_user):
    payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_fake_1",
                "subscription": "sub_fake_1",
                "metadata": {"user_id": test_user["user_id"], "tier_code": "lite"},
            }
        },
    }
    resp = client.post(
        "/api/subscription/webhook",
        data=json.dumps(payload),
        headers={"Stripe-Signature": "t=1,v1=fake", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["received"] == "checkout.session.completed"

    with app.app_context():
        from app.services import subscription_service as svc
        sub = svc.get_user_subscription(test_user["user_id"])

    assert sub["tier_code"] == "lite"
    assert sub["status"] == "active"
    assert sub["stripe_customer_id"] == "cus_fake_1"
    assert sub["stripe_subscription_id"] == "sub_fake_1"
    assert sub["current_period_end"] is not None
    assert FakeStripeClient.last_instance.v1.subscriptions.retrieve_calls[-1] == "sub_fake_1"


# ---------------------------------------------------------------------------
# Customer portal — depends on the subscription created by the webhook test above
# ---------------------------------------------------------------------------

def test_create_portal_session_uses_gateway(app, test_user):
    from app.services import subscription_service as svc

    with app.app_context():
        url = svc.create_portal_session(
            user_id=test_user["user_id"],
            return_url="https://example.com/account",
        )

    assert url == "https://billing.stripe.com/fake-portal"
    call = FakeStripeClient.last_instance.v1.billing_portal.sessions.calls[-1]
    assert call["customer"] == "cus_fake_1"


# ---------------------------------------------------------------------------
# Factory error handling
# ---------------------------------------------------------------------------

def test_factory_rejects_unknown_gateway(app):
    from app.services import payment_settings_service as pay_settings
    from app.services.payment import factory as payment_factory

    with app.app_context():
        pay_settings.set_setting(pay_settings.GATEWAY, "paypal")
        with pytest.raises(RuntimeError, match="未知的金流閘道"):
            payment_factory.get_active_gateway()


def test_factory_reserved_gateways_not_implemented(app):
    from app.services.payment import factory as payment_factory

    with app.app_context():
        with pytest.raises(RuntimeError, match="尚未支援"):
            payment_factory.get_gateway_by_type("payuni")
        with pytest.raises(RuntimeError, match="尚未支援"):
            payment_factory.get_gateway_by_type("shopline")


def test_factory_missing_secret_key_raises(app):
    from app.services import payment_settings_service as pay_settings
    from app.services.payment import factory as payment_factory

    with app.app_context():
        pay_settings.set_setting(pay_settings.STRIPE_SECRET_KEY, None)
        with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY"):
            payment_factory.get_active_gateway()
        # restore for subsequent tests
        pay_settings.set_setting(pay_settings.STRIPE_SECRET_KEY, "sk_test_fake_123")


# ---------------------------------------------------------------------------
# test_connection
# ---------------------------------------------------------------------------

def test_gateway_test_connection_success(app):
    from app.services.payment import factory as payment_factory

    with app.app_context():
        gateway = payment_factory.get_active_gateway()
        success, message = gateway.test_connection()

    assert success is True
    assert "測試" in message
    assert "TWD" in message and "USD" in message


def test_gateway_test_connection_failure(app):
    from app.services.payment import factory as payment_factory

    with app.app_context():
        gateway = payment_factory.get_active_gateway()
        gateway._client.v1.balance.should_fail = True
        success, message = gateway.test_connection()

    assert success is False
    assert "連線失敗" in message
