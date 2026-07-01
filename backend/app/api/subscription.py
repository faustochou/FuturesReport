"""
Subscription API routes.

POST /api/subscription/create-checkout-session
POST /api/subscription/webhook                  (Stripe webhook – no auth)
GET  /api/subscription/status
POST /api/subscription/create-portal-session
"""

import stripe

from flask import jsonify, request

from . import subscription_bp
from ..services import subscription_service as svc
from ..utils.auth import current_user, require_auth


# ---------------------------------------------------------------------------
# GET /api/subscription/status
# ---------------------------------------------------------------------------

@subscription_bp.route("/status", methods=["GET"])
@require_auth
def subscription_status():
    user = current_user()
    user_id = user["user_id"]

    sub = svc.get_user_subscription(user_id)
    tiers = svc.get_all_tiers()

    active_tier = None
    if sub:
        active_tier = svc.get_tier(sub["tier_code"])

    return jsonify({
        "success": True,
        "data": {
            "subscription": sub,
            "active_tier": active_tier,
            "available_tiers": [t for t in tiers if t["is_available"]],
        },
    })


# ---------------------------------------------------------------------------
# POST /api/subscription/create-checkout-session
# ---------------------------------------------------------------------------

@subscription_bp.route("/create-checkout-session", methods=["POST"])
@require_auth
def create_checkout_session():
    user = current_user()
    data = request.get_json() or {}
    tier_code = (data.get("tier_code") or "").strip().lower()

    if not tier_code:
        return jsonify({"success": False, "error": "tier_code 為必填欄位"}), 400

    # Build redirect URLs from the incoming request origin
    origin = request.headers.get("Origin") or request.host_url.rstrip("/")
    success_url = f"{origin}/subscription?checkout=success"
    cancel_url = f"{origin}/subscription?checkout=cancel"

    try:
        checkout_url = svc.create_checkout_session(
            user_id=user["user_id"],
            user_email=user.get("username"),  # username == email in most setups
            tier_code=tier_code,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503

    return jsonify({"success": True, "data": {"checkout_url": checkout_url}})


# ---------------------------------------------------------------------------
# POST /api/subscription/create-portal-session
# ---------------------------------------------------------------------------

@subscription_bp.route("/create-portal-session", methods=["POST"])
@require_auth
def create_portal_session():
    user = current_user()
    origin = request.headers.get("Origin") or request.host_url.rstrip("/")
    return_url = f"{origin}/subscription"

    try:
        portal_url = svc.create_portal_session(
            user_id=user["user_id"],
            return_url=return_url,
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503

    return jsonify({"success": True, "data": {"portal_url": portal_url}})


# ---------------------------------------------------------------------------
# POST /api/subscription/webhook  (no auth – verified via Stripe-Signature)
# ---------------------------------------------------------------------------

@subscription_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()          # raw bytes – must NOT use request.json
    sig_header = request.headers.get("Stripe-Signature", "")

    if not sig_header:
        return jsonify({"success": False, "error": "Missing Stripe-Signature"}), 400

    try:
        event = svc.construct_webhook_event(payload, sig_header)
    except stripe.SignatureVerificationError as exc:
        return jsonify({"success": False, "error": f"Webhook 簽名驗證失敗: {exc}"}), 400
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc)}), 503

    event_type = event["type"]
    event_data = event["data"]

    _HANDLERS = {
        "checkout.session.completed":      svc.handle_checkout_completed,
        "customer.subscription.updated":   svc.handle_subscription_updated,
        "customer.subscription.deleted":   svc.handle_subscription_deleted,
        "invoice.payment_failed":          svc.handle_invoice_payment_failed,
    }

    handler = _HANDLERS.get(event_type)
    if handler:
        try:
            handler(event_data)
        except Exception as exc:
            # Log but always return 200 so Stripe doesn't retry indefinitely
            from ..utils.logger import get_logger
            get_logger("futuresreport.subscription").error(
                "[Webhook] 處理 %s 時發生錯誤: %s", event_type, exc
            )

    # Always return 200 to acknowledge receipt
    return jsonify({"success": True, "received": event_type})
