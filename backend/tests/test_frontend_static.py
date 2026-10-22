"""
Tests for serving the production frontend build (frontend/dist) from Flask.

Production runs `vite build` at image-build time, so Flask serves the SPA shell and the
hashed assets next to the /api routes. These tests point FRONTEND_DIST_DIR at a temp
folder so they do not depend on a real frontend build.

Run from backend/ directory:
    pytest tests/test_frontend_static.py -v
"""

import os
import tempfile

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="futuresreport_static_")
os.close(_db_fd)
_dist_dir = tempfile.mkdtemp(prefix="futuresreport_dist_")

os.makedirs(os.path.join(_dist_dir, "assets"))
with open(os.path.join(_dist_dir, "index.html"), "w", encoding="utf-8") as fh:
    fh.write("<!doctype html><title>SPA-SHELL</title>")
with open(os.path.join(_dist_dir, "assets", "app-abc123.js"), "w", encoding="utf-8") as fh:
    fh.write("console.log('asset');")
with open(os.path.join(_dist_dir, "favicon.svg"), "w", encoding="utf-8") as fh:
    fh.write("<svg/>")

os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SECRET_KEY"] = "test-secret-key-for-static-tests"
os.environ["FLASK_DEBUG"] = "False"
# FRONTEND_DIST_DIR is deliberately NOT set here: setting it at import time would leak into
# every other test module during collection. The fixture below sets and removes it.


@pytest.fixture(scope="module")
def client():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # Re-assert: other test modules mutate these process-global env vars.
    os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
    os.environ["SECRET_KEY"] = "test-secret-key-for-static-tests"
    os.environ["FRONTEND_DIST_DIR"] = _dist_dir
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    yield application.test_client()
    os.environ.pop("FRONTEND_DIST_DIR", None)
    try:
        os.unlink(_db_path)
    except OSError:
        pass


def test_root_serves_spa_shell_uncached(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"SPA-SHELL" in resp.data
    assert resp.headers["Cache-Control"] == "no-cache"


def test_client_side_route_falls_back_to_spa_shell(client):
    resp = client.get("/launch/some/deep/link")
    assert resp.status_code == 200
    assert b"SPA-SHELL" in resp.data
    assert resp.headers["Cache-Control"] == "no-cache"


def test_hashed_asset_is_served_and_cached_long(client):
    resp = client.get("/assets/app-abc123.js")
    assert resp.status_code == 200
    assert b"console.log('asset')" in resp.data
    assert "immutable" in resp.headers["Cache-Control"]


def test_top_level_static_file_is_served(client):
    resp = client.get("/favicon.svg")
    assert resp.status_code == 200
    assert resp.data == b"<svg/>"


def test_unknown_api_path_is_404_not_spa_shell(client):
    for path in ("/api/does-not-exist", "/api"):
        resp = client.get(path)
        assert resp.status_code == 404, path
        assert b"SPA-SHELL" not in resp.data


def test_health_endpoint_still_wins_over_catch_all(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_real_api_routes_still_work(client):
    resp = client.get("/api/settings/social")
    assert resp.status_code == 200


@pytest.mark.parametrize("path", [
    "/../../etc/passwd",
    "/..%2f..%2fetc%2fpasswd",
    "/assets/../../../etc/passwd",
])
def test_path_traversal_never_leaks_files(client, path):
    resp = client.get(path)
    assert b"root:" not in resp.data
