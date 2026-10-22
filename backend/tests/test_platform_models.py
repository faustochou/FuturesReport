"""
Tests for site-provided ("platform") LLM models:
  admin CRUD            /api/admin/platform-models
  subscriber listing    GET /api/auth/platform-models
  selection             PUT /api/auth/platform-model
  LLM resolution        UserManager.get_llm_config()
  public plan listing   GET /api/subscription/tiers

Run from backend/ directory:
    pytest tests/test_platform_models.py -v
"""

import os
import tempfile

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="futuresreport_platmodel_")
os.close(_db_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-for-platform-models"
os.environ["FLASK_DEBUG"] = "False"

PLATFORM_KEY = "sk-platform-secret-1234567890"
OWN_KEY = "sk-user-own-key-abcdefghij"


@pytest.fixture(scope="module")
def app():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
    os.environ["SECRET_KEY"] = "test-secret-key-for-platform-models"
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


def _register(client, username):
    resp = client.post("/api/auth/register", json={
        "username": username, "password": "platformpass123",
    })
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    return data["token"], data["user"]["user_id"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin(client):
    # The first registered account becomes the admin.
    token, user_id = _register(client, "platmodel_admin")
    return {"token": token, "user_id": user_id}


@pytest.fixture(scope="module")
def lite_user(client, admin):
    token, user_id = _register(client, "platmodel_lite")
    resp = client.put(
        f"/api/admin/users/{user_id}/subscription",
        json={"tier_code": "lite"}, headers=_h(admin["token"]),
    )
    assert resp.status_code == 200
    return {"token": token, "user_id": user_id}


@pytest.fixture(scope="module")
def premium_user(client, admin):
    token, user_id = _register(client, "platmodel_premium")
    resp = client.put(
        f"/api/admin/users/{user_id}/subscription",
        json={"tier_code": "premium"}, headers=_h(admin["token"]),
    )
    assert resp.status_code == 200
    return {"token": token, "user_id": user_id}


@pytest.fixture(scope="module")
def model(client, admin):
    resp = client.post("/api/admin/platform-models", json={
        "provider": "openai", "model": "gpt-4o-mini",
        "label": "站方 GPT-4o mini", "api_key": PLATFORM_KEY,
    }, headers=_h(admin["token"]))
    assert resp.status_code == 201
    return resp.get_json()["data"]["model"]


# ---------------------------------------------------------------------------
# Admin CRUD
# ---------------------------------------------------------------------------

def test_admin_endpoints_require_admin(client, lite_user):
    assert client.get("/api/admin/platform-models").status_code == 401
    resp = client.get("/api/admin/platform-models", headers=_h(lite_user["token"]))
    assert resp.status_code == 401


def test_create_never_returns_api_key(client, model):
    assert model["provider"] == "openai"
    assert model["base_url"] == "https://api.openai.com/v1"
    assert model["is_enabled"] is True
    assert model["api_key_hint"] == "sk-p...7890"
    assert PLATFORM_KEY not in str(model)


def test_create_validation(client, admin):
    h = _h(admin["token"])
    assert client.post("/api/admin/platform-models", headers=h, json={
        "provider": "nope", "model": "x", "api_key": "k",
    }).status_code == 400
    assert client.post("/api/admin/platform-models", headers=h, json={
        "provider": "openai", "model": "gpt-4o", "api_key": "  ",
    }).status_code == 400


def test_api_key_is_encrypted_at_rest(app, model):
    from app.db.database import get_db
    from app.db.models import PlatformModel
    with get_db() as db:
        row = db.get(PlatformModel, model["id"])
        assert PLATFORM_KEY not in row.api_key_cipher


def test_update_keeps_key_when_blank(client, admin, model):
    h = _h(admin["token"])
    resp = client.put(f"/api/admin/platform-models/{model['id']}", headers=h, json={
        "label": "renamed", "api_key": "",
    })
    assert resp.status_code == 200
    assert resp.get_json()["data"]["model"]["label"] == "renamed"
    from app.services import platform_model_service as pms
    assert pms.get_credentials(model["id"])["api_key"] == PLATFORM_KEY


def test_update_unknown_is_404(client, admin):
    resp = client.put("/api/admin/platform-models/99999",
                      headers=_h(admin["token"]), json={"label": "x"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Entitlement + listing
# ---------------------------------------------------------------------------

def test_lite_user_gets_no_platform_models(client, lite_user, model):
    resp = client.get("/api/auth/platform-models", headers=_h(lite_user["token"]))
    data = resp.get_json()["data"]
    assert data["entitled"] is False
    assert data["models"] == []


def test_premium_user_sees_models_without_secrets(client, premium_user, model):
    resp = client.get("/api/auth/platform-models", headers=_h(premium_user["token"]))
    data = resp.get_json()["data"]
    assert data["entitled"] is True
    assert [m["id"] for m in data["models"]] == [model["id"]]
    assert "base_url" not in data["models"][0]
    assert PLATFORM_KEY not in resp.get_data(as_text=True)


def test_lite_user_cannot_select(client, lite_user, model):
    resp = client.put("/api/auth/platform-model", headers=_h(lite_user["token"]),
                      json={"platform_model_id": model["id"]})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Selection + LLM resolution
# ---------------------------------------------------------------------------

def test_select_platform_model_enables_llm_without_own_key(client, premium_user, model):
    from app.models.user import UserManager
    assert UserManager.get_llm_config(premium_user["user_id"]) is None

    resp = client.put("/api/auth/platform-model", headers=_h(premium_user["token"]),
                      json={"platform_model_id": model["id"]})
    assert resp.status_code == 200
    user = resp.get_json()["data"]["user"]
    assert user["llm_configured"] is True
    assert user["own_llm_configured"] is False
    assert user["llm_source"] == "platform"
    assert user["platform_model"]["id"] == model["id"]
    assert "api_key" not in str(user)

    cfg = UserManager.get_llm_config(premium_user["user_id"])
    assert cfg["api_key"] == PLATFORM_KEY
    assert cfg["model"] == "gpt-4o-mini"


def test_saving_own_key_switches_back_to_own_api(client, premium_user, model):
    from app.models.user import UserManager
    resp = client.put("/api/auth/llm-config", headers=_h(premium_user["token"]), json={
        "provider": "deepseek", "model": "deepseek-chat", "api_key": OWN_KEY,
    })
    assert resp.status_code == 200
    user = resp.get_json()["data"]["user"]
    assert user["llm_source"] == "own"
    assert user["platform_model"] is None
    assert UserManager.get_llm_config(premium_user["user_id"])["api_key"] == OWN_KEY

    # ...and the platform model can be re-selected without losing the own key.
    resp = client.put("/api/auth/platform-model", headers=_h(premium_user["token"]),
                      json={"platform_model_id": model["id"]})
    assert resp.get_json()["data"]["user"]["llm_source"] == "platform"
    resp = client.put("/api/auth/platform-model", headers=_h(premium_user["token"]),
                      json={"platform_model_id": None})
    user = resp.get_json()["data"]["user"]
    assert user["llm_source"] == "own"
    assert UserManager.get_llm_config(premium_user["user_id"])["api_key"] == OWN_KEY


def test_downgrade_stops_platform_model_use(client, admin, premium_user, model):
    from app.models.user import UserManager
    h = _h(admin["token"])
    client.put("/api/auth/platform-model", headers=_h(premium_user["token"]),
               json={"platform_model_id": model["id"]})
    client.put(f"/api/admin/users/{premium_user['user_id']}/subscription",
               json={"tier_code": "lite"}, headers=h)
    cfg = UserManager.get_llm_config(premium_user["user_id"])
    assert cfg["api_key"] == OWN_KEY      # falls back to the user's own key
    me = client.get("/api/auth/me", headers=_h(premium_user["token"])).get_json()
    assert me["data"]["user"]["llm_source"] == "own"
    client.put(f"/api/admin/users/{premium_user['user_id']}/subscription",
               json={"tier_code": "premium"}, headers=h)


def test_disabled_model_is_hidden_and_unusable(client, admin, premium_user, model):
    from app.models.user import UserManager
    h = _h(admin["token"])
    client.put("/api/auth/platform-model", headers=_h(premium_user["token"]),
               json={"platform_model_id": model["id"]})
    client.put(f"/api/admin/platform-models/{model['id']}", headers=h,
               json={"is_enabled": False})

    listing = client.get("/api/auth/platform-models", headers=_h(premium_user["token"]))
    assert listing.get_json()["data"]["models"] == []
    assert client.put("/api/auth/platform-model", headers=_h(premium_user["token"]),
                      json={"platform_model_id": model["id"]}).status_code == 400
    assert UserManager.get_llm_config(premium_user["user_id"])["api_key"] == OWN_KEY

    client.put(f"/api/admin/platform-models/{model['id']}", headers=h,
               json={"is_enabled": True})


def test_delete_model_clears_selection(client, admin, premium_user, model):
    h = _h(admin["token"])
    client.put("/api/auth/platform-model", headers=_h(premium_user["token"]),
               json={"platform_model_id": model["id"]})
    assert client.delete(f"/api/admin/platform-models/{model['id']}",
                         headers=h).status_code == 200
    assert client.delete(f"/api/admin/platform-models/{model['id']}",
                         headers=h).status_code == 404
    me = client.get("/api/auth/me", headers=_h(premium_user["token"])).get_json()
    assert me["data"]["user"]["platform_model"] is None
    assert client.get("/api/admin/platform-models", headers=h).get_json()["data"]["models"] == []


# ---------------------------------------------------------------------------
# Plan data
# ---------------------------------------------------------------------------

def test_seeded_plans_drop_agent_cap_and_premium_keeps_10_sims(client, admin):
    resp = client.get("/api/admin/subscription/tiers", headers=_h(admin["token"]))
    tiers = {t["tier_code"]: t for t in resp.get_json()["data"]["tiers"]}
    for t in tiers.values():
        assert "max_agents" not in t["feature_flags"]
    assert tiers["lite"]["feature_flags"]["sim_runs_per_month"] == 10
    assert tiers["premium"]["feature_flags"]["sim_runs_per_month"] == 10
    assert tiers["premium"]["feature_flags"]["platform_models"] is True


def test_public_tiers_requires_price_id_to_be_open(client, admin):
    h = _h(admin["token"])
    client.put("/api/admin/subscription/tiers/premium", headers=h,
               json={"is_available": True, "stripe_price_id": ""})
    tiers = client.get("/api/subscription/tiers").get_json()["data"]["tiers"]
    premium = next(t for t in tiers if t["tier_code"] == "premium")
    assert premium["is_available"] is False
    assert "stripe_price_id" not in premium

    client.put("/api/admin/subscription/tiers/premium", headers=h,
               json={"stripe_price_id": "price_test_premium"})
    tiers = client.get("/api/subscription/tiers").get_json()["data"]["tiers"]
    premium = next(t for t in tiers if t["tier_code"] == "premium")
    assert premium["is_available"] is True


# ---------------------------------------------------------------------------
# Stripe webhook plumbing (real stripe>=15 event objects have no .get())
# ---------------------------------------------------------------------------

def test_subscription_updated_follows_price_to_new_tier(app):
    import stripe
    from app.db.database import get_db
    from app.db.models import SubscriptionTier, UserSubscription
    from app.models.user import UserManager
    from app.services import subscription_service as svc

    user = UserManager.create_user("platmodel_switcher", "platformpass123")
    with app.app_context():
        with get_db() as db:
            tier = db.get(SubscriptionTier, "premium")
            tier.stripe_price_id = "price_test_premium"
        with get_db() as db:
            svc._upsert_subscription(
                db, user_id=user["user_id"], tier_code="lite",
                stripe_customer_id="cus_x", stripe_subscription_id="sub_switch_1",
                status="active", current_period_end=None,
            )

    event = stripe.Event.construct_from({
        "id": "evt_1", "type": "customer.subscription.updated",
        "data": {"object": {
            "id": "sub_switch_1", "status": "active",
            "items": {"data": [{"price": {"id": "price_test_premium"}}]},
        }},
    }, "sk_test")
    # Same conversion the webhook route performs.
    data = event["data"].to_dict()
    with app.app_context():
        svc.handle_subscription_updated(data)
        assert svc.get_user_subscription(user["user_id"])["tier_code"] == "premium"
