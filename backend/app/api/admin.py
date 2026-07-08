"""
Admin account management API.
"""

import json
import os

from flask import jsonify, request

from . import admin_bp
from ..models.user import UserManager
from ..utils.auth import current_admin, require_admin
from ..services import payment_settings_service as pay_settings
from ..services import refund_service
from ..services import subscription_service as sub_svc
from ..services.payment import factory as payment_factory


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


def _webhook_url() -> str:
    # Build from SITE_URL env var (required behind Zeabur reverse proxy, because
    # request.host_url returns the internal container address, not the public domain).
    site_url = os.environ.get("SITE_URL", "").strip().rstrip("/")
    if not site_url:
        proto = request.headers.get("X-Forwarded-Proto", request.scheme)
        host  = request.headers.get("X-Forwarded-Host", request.host)
        site_url = f"{proto}://{host}"
    return f"{site_url}/api/subscription/webhook"


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


@admin_bp.route("/users/<user_id>/subscription", methods=["PUT"])
@require_admin
def set_user_subscription(user_id: str):
    """Admin override: grant or revoke a subscription tier without Stripe."""
    data = request.get_json() or {}
    tier_code = (data.get("tier_code") or "").strip().lower() or None
    try:
        updated = UserManager.set_user_subscription(user_id, tier_code)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({
        "success": True,
        "data": {"user": UserManager.public_user(updated)},
    })


@admin_bp.route("/users/<user_id>/refund", methods=["POST"])
@require_admin
def refund_user(user_id: str):
    """Refund the user's most recent Stripe invoice and cancel the subscription
    immediately. Admin-manually-granted subscriptions (no stripe_subscription_id)
    are rejected — there is nothing to refund online."""
    data = request.get_json() or {}
    reason = (data.get("reason") or "").strip()
    if not reason:
        return jsonify({"success": False, "error": "退款原因為必填欄位"}), 400

    admin = current_admin()
    try:
        result = refund_service.refund_user_subscription(
            user_id=user_id,
            reason=reason,
            admin_user_id=admin["user_id"],
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except refund_service.RefundConflictError as exc:
        return jsonify({"success": False, "error": str(exc)}), 409
    except refund_service.RefundGatewayError as exc:
        return jsonify({"success": False, "error": str(exc)}), 502

    return jsonify({"success": True, "data": result})


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
# Stripe settings — kept for backward compatibility; superseded by the
# gateway-agnostic /payment/settings endpoints below.
# ---------------------------------------------------------------------------

@admin_bp.route("/stripe/settings", methods=["GET"])
@require_admin
def stripe_settings():
    """Return a safe summary of Stripe configuration status."""
    summary = sub_svc.get_stripe_settings_summary()
    summary["webhook_url"] = _webhook_url()
    return jsonify({"success": True, "data": {"stripe": summary}})


# ---------------------------------------------------------------------------
# Payment gateway settings (gateway-agnostic; Stripe implemented today)
# ---------------------------------------------------------------------------

# Gateway ids the dropdown may offer. Only "stripe" can actually be selected —
# the others are reserved (interface exists, "coming soon" in the UI).
_KNOWN_GATEWAYS = {"stripe", "payuni", "shopline"}
_SELECTABLE_GATEWAYS = {"stripe"}


@admin_bp.route("/payment/settings", methods=["GET"])
@require_admin
def get_payment_settings():
    """Active gateway + masked key hints (with effective source: db/env) for the admin UI."""
    snapshot = pay_settings.get_effective_settings()
    secret_key = pay_settings.get_stripe_secret_key() or ""

    return jsonify({
        "success": True,
        "data": {
            "gateway": pay_settings.get_active_gateway_type(),
            "stripe": {
                "secret_key":      snapshot[pay_settings.STRIPE_SECRET_KEY],
                "webhook_secret":  snapshot[pay_settings.STRIPE_WEBHOOK_SECRET],
                "publishable_key": snapshot[pay_settings.STRIPE_PUBLISHABLE_KEY],
            },
            "is_test_mode": secret_key.startswith("sk_test_"),
            "webhook_url": _webhook_url(),
        },
    })


@admin_bp.route("/payment/settings", methods=["PUT"])
@require_admin
def update_payment_settings():
    """Update the active gateway and/or Stripe keys. An empty string clears the
    DB override for that field (falls back to env). Values are never echoed back."""
    data = request.get_json() or {}

    if "gateway" in data:
        gateway = (data["gateway"] or "").strip().lower()
        if gateway and gateway not in _SELECTABLE_GATEWAYS:
            if gateway in _KNOWN_GATEWAYS:
                return jsonify({
                    "success": False,
                    "error": f"金流閘道「{gateway}」尚未支援，敬請期待。",
                }), 400
            return jsonify({"success": False, "error": f"未知的金流閘道：{gateway}"}), 400
        pay_settings.set_setting(pay_settings.GATEWAY, gateway or None)

    if "stripe_secret_key" in data:
        pay_settings.set_setting(pay_settings.STRIPE_SECRET_KEY, data["stripe_secret_key"])
    if "stripe_webhook_secret" in data:
        pay_settings.set_setting(pay_settings.STRIPE_WEBHOOK_SECRET, data["stripe_webhook_secret"])
    if "stripe_publishable_key" in data:
        pay_settings.set_setting(pay_settings.STRIPE_PUBLISHABLE_KEY, data["stripe_publishable_key"])

    return jsonify({"success": True, "data": {}})


@admin_bp.route("/payment/test-connection", methods=["POST"])
@require_admin
def test_payment_connection():
    """Verify the active gateway's configured credentials actually work."""
    try:
        gateway = payment_factory.get_active_gateway()
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    success, message = gateway.test_connection()
    return jsonify({"success": True, "data": {"success": success, "message": message}})


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


# ---------------------------------------------------------------------------
# Site settings – social links
# ---------------------------------------------------------------------------

_SOCIAL_KEYS = frozenset([
    "social_facebook", "social_x", "social_instagram",
    "social_threads", "social_github",
])


@admin_bp.route("/settings/social", methods=["GET"])
@require_admin
def get_social_settings():
    """Return current social link settings (admin view)."""
    from sqlalchemy import select as sa_select
    from ..db.database import get_db
    from ..db.models import SiteSettings
    with get_db() as db:
        rows = db.execute(
            sa_select(SiteSettings).where(SiteSettings.key.in_(_SOCIAL_KEYS))
        ).scalars().all()
        data = {r.key: r.value or "" for r in rows}
    for k in _SOCIAL_KEYS:
        data.setdefault(k, "")
    return jsonify({"success": True, "data": data})


@admin_bp.route("/settings/social", methods=["PUT"])
@require_admin
def update_social_settings():
    """Update social link URLs. Pass only the fields you want to change."""
    from datetime import datetime
    from sqlalchemy import select as sa_select
    from ..db.database import get_db
    from ..db.models import SiteSettings
    body = request.get_json() or {}
    updates = {k: str(v or "").strip() for k, v in body.items() if k in _SOCIAL_KEYS}
    if not updates:
        return jsonify({"success": False, "error": "No valid fields provided"}), 400

    now = datetime.utcnow()
    with get_db() as db:
        existing = {
            r.key: r
            for r in db.execute(
                sa_select(SiteSettings).where(SiteSettings.key.in_(updates.keys()))
            ).scalars().all()
        }
        for key, value in updates.items():
            if key in existing:
                existing[key].value = value
                existing[key].updated_at = now
            else:
                db.add(SiteSettings(key=key, value=value, updated_at=now))

    return jsonify({"success": True, "data": updates})


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
