"""
Tests for the simulation history soft-delete endpoint
(DELETE /api/simulation/records/<record_id>).

Records are seeded directly via the ORM (bypassing a real OASIS simulation
run) to keep these tests fast and independent of the simulation engine.

Run from backend/ directory:
    pytest tests/test_simulation_history_delete.py -v
"""

import os
import tempfile
from datetime import datetime

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="futuresreport_history_")
os.close(_db_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-for-history-delete"
os.environ["FLASK_DEBUG"] = "False"


@pytest.fixture(scope="module")
def app():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # Re-assert: other test modules mutate these same process-global env vars.
    os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
    os.environ["SECRET_KEY"] = "test-secret-key-for-history-delete"
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


@pytest.fixture(scope="module", autouse=True)
def _consume_admin_slot(client):
    """The first user registered in this process becomes admin (repo convention,
    see UserManager.register / user.py:347). Burn that slot on a throwaway user
    first so every user registered by the tests below is a regular (non-admin)
    user — otherwise whichever test runs first would silently get an admin
    bypass on the subscription check."""
    client.post("/api/auth/register", json={
        "username": "history_admin_slot_holder",
        "password": "historytestpass123",
    })


def _register_user(client, username):
    resp = client.post("/api/auth/register", json={
        "username": username,
        "password": "historytestpass123",
    })
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    return data["user"]["user_id"], data["token"]


def _seed_active_subscription(app, user_id, tier_code="lite"):
    """Directly upsert an active paid-tier subscription row (no Stripe involved)."""
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
                    tier_code=tier_code,
                    status="active",
                    created_at=now,
                    updated_at=now,
                ))
            else:
                row.tier_code = tier_code
                row.status = "active"
                row.touch()


def _create_record(app, user_id, simulation_id, *, status="completed", title="test requirement"):
    from app.db.database import get_db
    from app.db.models import SimulationRecord

    now = datetime.utcnow()
    with app.app_context():
        with get_db() as db:
            record = SimulationRecord(
                user_id=user_id,
                simulation_id=simulation_id,
                project_id=None,
                title=title,
                report_filenames=[],
                started_at=now,
                status=status,
                created_at=now,
            )
            db.add(record)
            db.flush()
            return record.id


# ---------------------------------------------------------------------------
# 1. Free-tier user (no subscription at all) -> 403 SUBSCRIPTION_REQUIRED
# ---------------------------------------------------------------------------

def test_delete_requires_subscription_free_tier_403(app, client):
    user_id, token = _register_user(client, "history_free_user")
    record_id = _create_record(app, user_id, "sim_free_test_1")

    resp = client.delete(
        f"/api/simulation/records/{record_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    body = resp.get_json()
    assert body["success"] is False
    assert body["code"] == "SUBSCRIPTION_REQUIRED"


# ---------------------------------------------------------------------------
# 2. Not the owner (different, non-admin user) -> 403 ACCESS_DENIED,
#    even when the requester themselves has a paid plan.
# ---------------------------------------------------------------------------

def test_delete_not_owner_403(app, client):
    owner_id, _owner_token = _register_user(client, "history_owner_user")
    record_id = _create_record(app, owner_id, "sim_owner_test_1")

    other_id, other_token = _register_user(client, "history_other_user")
    _seed_active_subscription(app, other_id)

    resp = client.delete(
        f"/api/simulation/records/{record_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403
    body = resp.get_json()
    assert body["success"] is False
    assert body["code"] == "ACCESS_DENIED"


# ---------------------------------------------------------------------------
# 3. Simulation still running/preparing -> 409 SIMULATION_RUNNING
# ---------------------------------------------------------------------------

def test_delete_blocked_while_running_409(app, client):
    user_id, token = _register_user(client, "history_running_user")
    _seed_active_subscription(app, user_id)
    record_id = _create_record(app, user_id, "sim_running_test_1", status="running")

    resp = client.delete(
        f"/api/simulation/records/{record_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    body = resp.get_json()
    assert body["success"] is False
    assert body["code"] == "SIMULATION_RUNNING"


# ---------------------------------------------------------------------------
# 4. Owner + paid tier + not running -> soft-deleted; disappears from both
#    the list and detail endpoints afterwards.
# ---------------------------------------------------------------------------

def test_delete_success_removes_from_list(app, client):
    user_id, token = _register_user(client, "history_success_user")
    _seed_active_subscription(app, user_id)
    record_id = _create_record(app, user_id, "sim_success_test_1", status="completed")

    headers = {"Authorization": f"Bearer {token}"}

    list_before = client.get("/api/simulation/records", headers=headers)
    assert any(r["id"] == record_id for r in list_before.get_json()["data"])

    resp = client.delete(f"/api/simulation/records/{record_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["data"]["record_id"] == record_id
    assert body["data"]["simulation_id"] == "sim_success_test_1"

    list_after = client.get("/api/simulation/records", headers=headers)
    assert all(r["id"] != record_id for r in list_after.get_json()["data"])

    # Detail endpoint should now 404 too — the deleted_at filter applies there as well.
    detail_resp = client.get(f"/api/simulation/records/{record_id}", headers=headers)
    assert detail_resp.status_code == 404

    # Deleting again should also 404 (already soft-deleted, no longer "found").
    resp_again = client.delete(f"/api/simulation/records/{record_id}", headers=headers)
    assert resp_again.status_code == 404
