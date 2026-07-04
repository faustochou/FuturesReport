"""
Smoke tests for core API endpoints.

Validates response status codes and key fields WITHOUT calling external services
(Zep, Stripe, LLM). All tests run against a temp SQLite file that is created
fresh for each test session and deleted on teardown.

Run from backend/ directory:
    pytest tests/test_smoke.py -v
"""

import os
import tempfile
import pytest

# Must be set BEFORE the app is imported so the config module picks them up.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="futuresreport_smoke_")
os.close(_db_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-for-smoke-tests"
os.environ["FLASK_DEBUG"] = "False"


@pytest.fixture(scope="module")
def app():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    yield application
    # Teardown: delete temp db file
    try:
        os.unlink(_db_path)
    except OSError:
        pass


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def auth_token(client):
    """Register a test user and return its JWT token."""
    resp = client.post("/api/auth/register", json={
        "username": "smoketest_admin",
        "password": "smokepass123"
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["success"] is True
    assert "token" in data["data"]
    return data["data"]["token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

def test_providers(client):
    resp = client.get("/api/auth/providers")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "providers" in data["data"]
    providers = data["data"]["providers"]
    # DashScope / Qwen must be present
    assert "qwen" in providers
    assert "openai" in providers


def test_register_duplicate_fails(client, auth_token):
    resp = client.post("/api/auth/register", json={
        "username": "smoketest_admin",
        "password": "smokepass123"
    })
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_login(client):
    resp = client.post("/api/auth/login", json={
        "username": "smoketest_admin",
        "password": "smokepass123"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "token" in data["data"]


def test_login_wrong_password(client):
    resp = client.post("/api/auth/login", json={
        "username": "smoketest_admin",
        "password": "wrongpassword"
    })
    assert resp.status_code == 401
    assert resp.get_json()["success"] is False


def test_me(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    user = data["data"]["user"]
    assert "username" in user
    assert "role" in user
    # First registered user must be admin
    assert user["role"] == "admin"
    assert user["is_admin"] is True


def test_me_without_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    data = resp.get_json()
    assert data["success"] is False
    assert data["code"] == "AUTH_REQUIRED"


def test_logout(client, auth_headers):
    resp = client.post("/api/auth/logout", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


# ---------------------------------------------------------------------------
# Admin endpoints (RBAC: first user is admin)
# ---------------------------------------------------------------------------

def test_admin_login(client):
    resp = client.post("/api/admin/login", json={
        "username": "smoketest_admin",
        "password": "smokepass123"
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "token" in data["data"]


def test_admin_login_wrong_creds(client):
    resp = client.post("/api/admin/login", json={
        "username": "notexist",
        "password": "badpass"
    })
    assert resp.status_code == 401


def test_admin_dashboard(client, auth_headers):
    resp = client.get("/api/admin/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "stats" in data["data"]


def test_admin_list_users(client, auth_headers):
    resp = client.get("/api/admin/users", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert isinstance(data["data"]["users"], list)
    assert len(data["data"]["users"]) >= 1


def test_admin_list_tiers(client, auth_headers):
    resp = client.get("/api/admin/subscription/tiers", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    tiers = data["data"]["tiers"]
    tier_codes = [t["tier_code"] for t in tiers]
    # All three subscription tiers must exist
    assert "lite" in tier_codes
    assert "premium" in tier_codes
    assert "pro" in tier_codes


# ---------------------------------------------------------------------------
# Subscription endpoints
# ---------------------------------------------------------------------------

def test_subscription_status(client, auth_headers):
    resp = client.get("/api/subscription/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "subscription" in data["data"]
    assert "available_tiers" in data["data"]


def test_subscription_status_no_auth(client):
    resp = client.get("/api/subscription/status")
    assert resp.status_code == 401


def test_webhook_missing_signature(client):
    resp = client.post("/api/subscription/webhook", data=b'{}')
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


# ---------------------------------------------------------------------------
# Graph endpoints (no external Zep call needed for list/project endpoints)
# ---------------------------------------------------------------------------

def test_graph_project_list(client):
    resp = client.get("/api/graph/project/list")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


def test_graph_project_not_found(client):
    resp = client.get("/api/graph/project/nonexistent_id")
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_graph_task_list(client):
    resp = client.get("/api/graph/tasks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


# ---------------------------------------------------------------------------
# Simulation endpoints
# ---------------------------------------------------------------------------

def test_simulation_list(client):
    resp = client.get("/api/simulation/list")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


def test_simulation_history(client):
    resp = client.get("/api/simulation/history")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


def test_simulation_not_found(client):
    resp = client.get("/api/simulation/nonexistent_sim")
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


# ---------------------------------------------------------------------------
# Report endpoints
# ---------------------------------------------------------------------------

def test_report_list(client):
    resp = client.get("/api/report/list")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


def test_report_not_found(client):
    resp = client.get("/api/report/nonexistent_report")
    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_report_generate_requires_auth(client):
    resp = client.post("/api/report/generate", json={"simulation_id": "x"})
    assert resp.status_code == 401


def test_report_chat_requires_auth(client):
    resp = client.post("/api/report/chat", json={"simulation_id": "x", "message": "hi"})
    assert resp.status_code == 401
