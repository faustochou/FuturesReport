"""
Tests for the admin refund flow (Phase 3): atomic claim / rollback / cancel,
mirroring shineyang's markAsRefunded three-line-of-defence pattern.

Monkeypatches the Stripe SDK so no network calls are made.

Run from backend/ directory:
    pytest tests/test_refund_service.py -v
"""

import json
import os
import tempfile
import threading
import types

import pytest
import stripe

_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="futuresreport_refund_")
os.close(_db_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-for-refund-service"
os.environ["FLASK_DEBUG"] = "False"


# ---------------------------------------------------------------------------
# Fake Stripe SDK — only the surface the refund flow touches
# ---------------------------------------------------------------------------

class FakeSubscriptions:
    def __init__(self):
        self.cancel_calls = []
        self.cancel_should_fail = False

    def retrieve(self, sub_id, params=None, options=None):
        return types.SimpleNamespace(latest_invoice="in_fake_1", current_period_end=None)

    def cancel(self, sub_id, params=None, options=None):
        self.cancel_calls.append(sub_id)
        if self.cancel_should_fail:
            raise stripe.StripeError("cancel failed")
        return types.SimpleNamespace(id=sub_id, status="canceled")


class FakeInvoices:
    def retrieve(self, invoice_id, params=None, options=None):
        return types.SimpleNamespace(payment_intent="pi_fake_1")


class FakeRefunds:
    def __init__(self):
        self.calls = []
        self.should_fail = False

    def create(self, params=None, options=None):
        self.calls.append({"params": params, "options": options})
        if self.should_fail:
            raise stripe.StripeError("card issuer declined the refund")
        return types.SimpleNamespace(id="re_fake_1", amount=9900, currency="twd")


class FakeV1:
    def __init__(self):
        self.subscriptions = FakeSubscriptions()
        self.invoices = FakeInvoices()
        self.refunds = FakeRefunds()


class FakeStripeClient:
    last_instance = None

    def __init__(self, secret_key):
        self.secret_key = secret_key
        self.v1 = FakeV1()
        FakeStripeClient.last_instance = self


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
    os.environ["SECRET_KEY"] = "test-secret-key-for-refund-service"
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
def admin(client):
    """The first user registered in this module becomes admin (repo convention);
    every test reuses this admin to authorize the refund call, while each test
    registers its own separate subject user to refund."""
    resp = client.post("/api/auth/register", json={
        "username": "refund_test_admin",
        "password": "refundadminpass123",
    })
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    return {"user_id": data["user"]["user_id"], "token": data["token"]}


@pytest.fixture(autouse=True)
def _patch_stripe_sdk(monkeypatch):
    monkeypatch.setattr(stripe, "StripeClient", FakeStripeClient)


@pytest.fixture(autouse=True)
def _configure_payment_settings(app):
    from app.services import payment_settings_service as pay_settings

    with app.app_context():
        pay_settings.set_setting(pay_settings.STRIPE_SECRET_KEY, "sk_test_fake_123")
        pay_settings.set_setting(pay_settings.STRIPE_WEBHOOK_SECRET, "whsec_fake_123")
    yield


def _register_user(client, username):
    resp = client.post("/api/auth/register", json={
        "username": username,
        "password": "refundpass123",
    })
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    return data["user"]["user_id"], data["token"]


def _seed_stripe_subscription(app, user_id, *, status="active",
                               stripe_subscription_id="sub_fake_1",
                               stripe_customer_id="cus_fake_1"):
    from datetime import datetime
    from app.db.database import get_db
    from app.db.models import UserSubscription
    from sqlalchemy import select

    with app.app_context():
        with get_db() as db:
            row = db.execute(
                select(UserSubscription).where(UserSubscription.user_id == user_id)
            ).scalar_one_or_none()
            now = datetime.utcnow()
            if row is None:
                db.add(UserSubscription(
                    user_id=user_id,
                    tier_code="lite",
                    stripe_customer_id=stripe_customer_id,
                    stripe_subscription_id=stripe_subscription_id,
                    status=status,
                    created_at=now,
                    updated_at=now,
                ))
            else:
                row.stripe_customer_id = stripe_customer_id
                row.stripe_subscription_id = stripe_subscription_id
                row.status = status
                row.touch()


def _get_subscription_status(app, user_id):
    from app.services import subscription_service as sub_svc
    with app.app_context():
        sub = sub_svc.get_user_subscription(user_id)
        return sub["status"] if sub else None


# ---------------------------------------------------------------------------
# Happy path — full route: refund + cancel + audit row
# ---------------------------------------------------------------------------

def test_refund_success_cancels_subscription_and_records_audit_row(app, client, admin):
    user_id, _token = _register_user(client, "refund_subject_1")
    _seed_stripe_subscription(app, user_id)

    resp = client.post(
        f"/api/admin/users/{user_id}/refund",
        json={"reason": "客戶要求退款"},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["refund_id"] == "re_fake_1"
    assert body["data"]["requires_manual_action"] is False

    assert _get_subscription_status(app, user_id) == "canceled"
    assert FakeStripeClient.last_instance.v1.subscriptions.cancel_calls == ["sub_fake_1"]

    with app.app_context():
        from app.db.database import get_db
        from app.db.models import RefundRecord
        from sqlalchemy import select
        with get_db() as db:
            record = db.execute(
                select(RefundRecord).where(RefundRecord.user_id == user_id)
            ).scalar_one()
            assert record.stripe_refund_id == "re_fake_1"
            assert record.stripe_subscription_id == "sub_fake_1"
            assert record.stripe_payment_intent_id == "pi_fake_1"
            assert record.amount == 9900
            assert record.currency == "twd"
            assert record.reason == "客戶要求退款"
            assert record.admin_user_id == admin["user_id"]


def test_refund_requires_nonempty_reason(app, client, admin):
    user_id, _token = _register_user(client, "refund_subject_reason")
    _seed_stripe_subscription(app, user_id, stripe_subscription_id="sub_reason_1")

    resp = client.post(
        f"/api/admin/users/{user_id}/refund",
        json={"reason": "  "},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# Idempotency key format
# ---------------------------------------------------------------------------

def test_idempotency_key_format(app, client, admin):
    user_id, _token = _register_user(client, "refund_subject_idem")
    _seed_stripe_subscription(app, user_id, stripe_subscription_id="sub_idem_1")

    resp = client.post(
        f"/api/admin/users/{user_id}/refund",
        json={"reason": "test idempotency"},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert resp.status_code == 200

    last_call = FakeStripeClient.last_instance.v1.refunds.calls[-1]
    assert last_call["options"]["idempotency_key"] == "refund_in_fake_1"
    assert last_call["params"]["payment_intent"] == "pi_fake_1"


# ---------------------------------------------------------------------------
# Stripe failure -> rollback
# ---------------------------------------------------------------------------

def test_stripe_refund_failure_rolls_back_claim(app, client, admin):
    user_id, _token = _register_user(client, "refund_subject_fail")
    _seed_stripe_subscription(app, user_id, stripe_subscription_id="sub_fail_1")

    # The gateway factory builds a fresh StripeClient per call, so make the
    # *class* fail-by-default for the duration of this test.
    original_client_cls = stripe.StripeClient

    class FailingRefundsStripeClient(FakeStripeClient):
        def __init__(self, secret_key):
            super().__init__(secret_key)
            self.v1.refunds.should_fail = True

    stripe.StripeClient = FailingRefundsStripeClient
    try:
        resp = client.post(
            f"/api/admin/users/{user_id}/refund",
            json={"reason": "should fail"},
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    finally:
        stripe.StripeClient = original_client_cls

    assert resp.status_code == 502
    assert resp.get_json()["success"] is False

    # Claim must be rolled back to the original "active" status, not stuck at "refunding"
    assert _get_subscription_status(app, user_id) == "active"


# ---------------------------------------------------------------------------
# Cancel failure after a successful refund -> requires_manual_action
# ---------------------------------------------------------------------------

def test_cancel_failure_after_refund_reports_requires_manual_action(app, client, admin):
    user_id, _token = _register_user(client, "refund_subject_cancelfail")
    _seed_stripe_subscription(app, user_id, stripe_subscription_id="sub_cancelfail_1")

    class CancelFailingStripeClient(FakeStripeClient):
        def __init__(self, secret_key):
            super().__init__(secret_key)
            self.v1.subscriptions.cancel_should_fail = True

    original_client_cls = stripe.StripeClient
    stripe.StripeClient = CancelFailingStripeClient
    try:
        resp = client.post(
            f"/api/admin/users/{user_id}/refund",
            json={"reason": "cancel will fail"},
            headers={"Authorization": f"Bearer {admin['token']}"},
        )
    finally:
        stripe.StripeClient = original_client_cls

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["requires_manual_action"] is True
    # Refund already succeeded, so status is still finalized to canceled locally
    assert _get_subscription_status(app, user_id) == "canceled"


# ---------------------------------------------------------------------------
# Admin-manually-granted subscription (no Stripe id) is rejected
# ---------------------------------------------------------------------------

def test_admin_granted_subscription_without_stripe_id_is_rejected(app, client, admin):
    user_id, _token = _register_user(client, "refund_subject_manual")
    from app.models.user import UserManager
    with app.app_context():
        UserManager.set_user_subscription(user_id, "lite")

    resp = client.post(
        f"/api/admin/users/{user_id}/refund",
        json={"reason": "attempt refund on manual grant"},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert resp.status_code == 400
    assert "非經 Stripe 建立" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# Double-click via the API: second call after the first finalizes -> 409/400
# ---------------------------------------------------------------------------

def test_double_click_second_request_after_completion_is_rejected(app, client, admin):
    user_id, _token = _register_user(client, "refund_subject_doubleclick")
    _seed_stripe_subscription(app, user_id, stripe_subscription_id="sub_dc_1")

    resp1 = client.post(
        f"/api/admin/users/{user_id}/refund",
        json={"reason": "first click"},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    assert resp1.status_code == 200

    resp2 = client.post(
        f"/api/admin/users/{user_id}/refund",
        json={"reason": "second click"},
        headers={"Authorization": f"Bearer {admin['token']}"},
    )
    # Subscription is now "canceled" — not a claimable status — so the second
    # attempt fails the atomic claim (409).
    assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# True concurrency: only one of N racing claims may succeed
# ---------------------------------------------------------------------------

def test_concurrent_claims_only_one_succeeds(app, client):
    from app.services import refund_service

    user_id, _token = _register_user(client, "refund_concurrent_user")
    _seed_stripe_subscription(app, user_id, stripe_subscription_id="sub_concurrent_1")

    results = []
    lock = threading.Lock()

    def attempt():
        with app.app_context():
            outcome = refund_service.claim_subscription_for_refund(user_id)
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=attempt) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = [r for r in results if r is not None]
    assert len(successes) == 1
    assert successes[0] == "active"
