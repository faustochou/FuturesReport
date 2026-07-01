"""
Admin account management API.
"""

import json
import os

from flask import jsonify, request

from . import admin_bp
from ..models.user import UserManager
from ..utils.auth import current_admin, require_admin
from ..services import subscription_service as sub_svc


def _version_history_path() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../version-history.json")
    )


def _runtime_commit() -> str:
    for key in (
        "ZEABUR_GIT_COMMIT_SHA",
        "VERCEL_GIT_COMMIT_SHA",
        "SOURCE_COMMIT",
        "GIT_COMMIT_SHA",
    ):
        value = os.environ.get(key)
        if value:
            return value[:7]
    return "current deployment"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@admin_bp.route("/login", methods=["POST"])
def admin_login():
    data = request.get_json() or {}
    user = UserManager.authenticate(
        username=data.get("username", ""),
        password=data.get("password", ""),
    )
    if not user or user.get("role") != "admin":
        return jsonify({
            "success": False,
            "error": "Invalid admin username or password.",
        }), 401

    return jsonify({
        "success": True,
        "data": {
            "token": UserManager.issue_admin_token(user["user_id"]),
            "admin": {
                "user_id": user["user_id"],
                "username": user["username"],
                "role": user.get("role", "admin"),
            },
        },
    })


@admin_bp.route("/me", methods=["GET"])
@require_admin
def admin_me():
    return jsonify({
        "success": True,
        "data": {"admin": current_admin()},
    })


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

@admin_bp.route("/dashboard", methods=["GET"])
@require_admin
def dashboard():
    stats = UserManager.get_stats()
    try:
        import psutil
        vm = psutil.virtual_memory()
        system = {
            "memory_percent": vm.percent,
            "memory_available_mb": round(vm.available / 1024 / 1024, 1),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
        }
    except Exception:
        system = {}
    return jsonify({
        "success": True,
        "data": {"stats": stats, "system": system},
    })


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

@admin_bp.route("/users", methods=["GET"])
@require_admin
def list_users():
    return jsonify({
        "success": True,
        "data": {
            "users": UserManager.list_public_users(),
            "providers": UserManager.providers(),
        },
    })


@admin_bp.route("/users/<user_id>", methods=["PUT"])
@require_admin
def update_user(user_id: str):
    data = request.get_json() or {}
    try:
        updated = UserManager.update_user(
            user_id=user_id,
            username=data.get("username"),
            password=data.get("password"),
            llm_config=data.get("llm"),
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    return jsonify({
        "success": True,
        "data": {"user": UserManager.public_user(updated)},
    })


@admin_bp.route("/users/<user_id>/role", methods=["PUT"])
@require_admin
def change_role(user_id: str):
    """Promote or demote a user (admin ↔ user)."""
    data = request.get_json() or {}
    role = (data.get("role") or "").strip().lower()
    if role not in ("admin", "user"):
        return jsonify({"success": False, "error": "role must be 'admin' or 'user'"}), 400
    try:
        updated = UserManager.update_user(user_id=user_id, role=role)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({
        "success": True,
        "data": {"user": UserManager.public_user(updated)},
    })


@admin_bp.route("/users/<user_id>/active", methods=["PUT"])
@require_admin
def toggle_active(user_id: str):
    """Enable or disable a user account."""
    data = request.get_json() or {}
    if "is_active" not in data:
        return jsonify({"success": False, "error": "is_active field required"}), 400
    try:
        updated = UserManager.update_user(
            user_id=user_id, is_active=bool(data["is_active"])
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({
        "success": True,
        "data": {"user": UserManager.public_user(updated)},
    })


@admin_bp.route("/users/<user_id>", methods=["DELETE"])
@require_admin
def delete_user(user_id: str):
    """Permanently delete a user and their LLM config."""
    try:
        UserManager.delete_user(user_id)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "data": {}})


# ---------------------------------------------------------------------------
# Version history
# ---------------------------------------------------------------------------

@admin_bp.route("/versions", methods=["GET"])
@require_admin
def version_history():
    path = _version_history_path()
    if not os.path.exists(path):
        return jsonify({"success": True, "data": {"versions": []}})

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    versions = data.get("versions", [])
    for item in versions:
        if item.get("commit") == "pending":
            item["commit"] = _runtime_commit()

    return jsonify({"success": True, "data": {"versions": versions}})


# ---------------------------------------------------------------------------
# Stripe settings (read-only for now; keys are managed via env vars)
# ---------------------------------------------------------------------------

@admin_bp.route("/stripe/settings", methods=["GET"])
@require_admin
def stripe_settings():
    """Return a safe summary of Stripe configuration status."""
    summary = sub_svc.get_stripe_settings_summary()
    # Append the full webhook URL so admin can copy-paste it into Stripe Dashboard
    summary["webhook_url"] = request.host_url.rstrip("/") + "/api/subscription/webhook"
    return jsonify({"success": True, "data": {"stripe": summary}})


# ---------------------------------------------------------------------------
# Subscription tier management
# ---------------------------------------------------------------------------

@admin_bp.route("/subscription/tiers", methods=["GET"])
@require_admin
def list_tiers():
    return jsonify({
        "success": True,
        "data": {"tiers": sub_svc.get_all_tiers()},
    })


@admin_bp.route("/subscription/tiers/<tier_code>", methods=["PUT"])
@require_admin
def update_tier(tier_code: str):
    """Update a tier's is_available, stripe_price_id, or feature_flags."""
    data = request.get_json() or {}

    kwargs = {}
    if "is_available" in data:
        kwargs["is_available"] = bool(data["is_available"])
    if "stripe_price_id" in data:
        kwargs["stripe_price_id"] = str(data["stripe_price_id"] or "")
    if "feature_flags" in data:
        if not isinstance(data["feature_flags"], dict):
            return jsonify({
                "success": False,
                "error": "feature_flags 必須是 JSON 物件",
            }), 400
        kwargs["feature_flags"] = data["feature_flags"]

    if not kwargs:
        return jsonify({"success": False, "error": "沒有可更新的欄位"}), 400

    try:
        updated = sub_svc.update_tier(tier_code, **kwargs)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404

    return jsonify({"success": True, "data": {"tier": updated}})
