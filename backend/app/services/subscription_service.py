"""
Stripe subscription service.

All Stripe API calls go through this module.  The service is intentionally
stateless: no caching of tier data so admin toggles take effect immediately.

stripe SDK >= 10.0: uses StripeClient.v1.* for API calls,
and the module-level stripe.Webhook.construct_event() for webhook verification.
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import stripe

from ..db.database import get_db
from ..db.models import SubscriptionTier, UserSubscription
from ..utils.logger import get_logger
from sqlalchemy import select

logger = get_logger("futuresreport.subscription")


# ---------------------------------------------------------------------------
# Stripe client initialisation
# ---------------------------------------------------------------------------

def _get_stripe_client() -> stripe.StripeClient:
    """Lazy-initialise Stripe client.  Raises RuntimeError if key is missing."""
    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        raise RuntimeError(
            "STRIPE_SECRET_KEY 未設定。請在 .env 或 Zeabur 環境變數中填入。"
        )
    return stripe.StripeClient(secret_key)


def is_stripe_configured() -> bool:
    """Return True only when all required Stripe env vars are present."""
    return bool(
        os.environ.get("STRIPE_SECRET_KEY", "").strip()
        and os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    )


def get_stripe_settings_summary() -> Dict[str, Any]:
    """Safe summary for the admin UI — never exposes secret key plaintext."""
    secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    publishable_key = os.environ.get("STRIPE_PUBLISHABLE_KEY", "").strip()

    def mask(key: str) -> Optional[str]:
        if not key:
            return None
        return f"{key[:7]}...{key[-4:]}"

    return {
        "is_configured": is_stripe_configured(),
        "secret_key_hint": mask(secret_key),
        "publishable_key_hint": mask(publishable_key),
        "is_test_mode": secret_key.startswith("sk_test_"),
        "webhook_configured": bool(webhook_secret),
        # Full URL is constructed by the admin API using request.host_url
        "webhook_path": "/api/subscription/webhook",
    }


# ---------------------------------------------------------------------------
# Tier helpers
# ---------------------------------------------------------------------------

def get_all_tiers() -> List[Dict[str, Any]]:
    with get_db() as db:
        rows = db.execute(
            select(SubscriptionTier).order_by(SubscriptionTier.tier_code)
        ).scalars().all()
        return [_tier_to_dict(t) for t in rows]


def get_tier(tier_code: str) -> Optional[Dict[str, Any]]:
    with get_db() as db:
        row = db.execute(
            select(SubscriptionTier).where(
                SubscriptionTier.tier_code == tier_code
            )
        ).scalar_one_or_none()
        return _tier_to_dict(row) if row else None


def update_tier(
    tier_code: str,
    *,
    is_available: Optional[bool] = None,
    stripe_price_id: Optional[str] = None,
    feature_flags: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    with get_db() as db:
        row = db.execute(
            select(SubscriptionTier).where(
                SubscriptionTier.tier_code == tier_code
            )
        ).scalar_one_or_none()
        if row is None:
            raise ValueError(f"未知方案代碼：{tier_code}")

        if is_available is not None:
            row.is_available = bool(is_available)
        if stripe_price_id is not None:
            row.stripe_price_id = stripe_price_id.strip() or None
        if feature_flags is not None:
            row.feature_flags = feature_flags
        row.touch()
        db.flush()
        return _tier_to_dict(row)


def _tier_to_dict(t: SubscriptionTier) -> Dict[str, Any]:
    return {
        "tier_code": t.tier_code,
        "display_name": t.display_name,
        "stripe_price_id": t.stripe_price_id,
        "is_available": t.is_available,
        "feature_flags": t.feature_flags,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


# ---------------------------------------------------------------------------
# User subscription helpers
# ---------------------------------------------------------------------------

def get_user_subscription(user_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as db:
        row = db.execute(
            select(UserSubscription).where(
                UserSubscription.user_id == user_id
            )
        ).scalar_one_or_none()
        return _sub_to_dict(row) if row else None


def _sub_to_dict(s: UserSubscription) -> Dict[str, Any]:
    return {
        "tier_code": s.tier_code,
        "stripe_customer_id": s.stripe_customer_id,
        "stripe_subscription_id": s.stripe_subscription_id,
        "status": s.status,
        "current_period_end": (
            s.current_period_end.isoformat() if s.current_period_end else None
        ),
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _upsert_subscription(
    db,
    *,
    user_id: str,
    tier_code: str,
    stripe_customer_id: Optional[str],
    stripe_subscription_id: Optional[str],
    status: str,
    current_period_end: Optional[datetime],
) -> UserSubscription:
    """Insert or update the user's subscription row (idempotent)."""
    row = db.execute(
        select(UserSubscription).where(
            UserSubscription.user_id == user_id
        )
    ).scalar_one_or_none()

    now = datetime.utcnow()
    if row is None:
        row = UserSubscription(
            user_id=user_id,
            tier_code=tier_code,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            status=status,
            current_period_end=current_period_end,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.tier_code = tier_code
        if stripe_customer_id:
            row.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id:
            row.stripe_subscription_id = stripe_subscription_id
        row.status = status
        row.current_period_end = current_period_end
        row.touch()

    db.flush()
    return row


# ---------------------------------------------------------------------------
# Permission check (shared by all feature-gated routes)
# ---------------------------------------------------------------------------

def check_feature(user_id: str, feature_key: str) -> bool:
    """Return True if the user's active subscription grants this feature.

    Tier feature_flags are edited in the DB by admins — no code change needed
    when adding or removing features from a plan.
    """
    sub = get_user_subscription(user_id)
    if not sub or sub["status"] not in ("active", "trialing"):
        return False

    tier = get_tier(sub["tier_code"])
    if not tier or not tier["is_available"]:
        return False

    flags = tier.get("feature_flags") or {}
    return bool(flags.get(feature_key, False))


# ---------------------------------------------------------------------------
# Stripe Checkout Session
# ---------------------------------------------------------------------------

def create_checkout_session(
    *,
    user_id: str,
    user_email: Optional[str],
    tier_code: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout Session and return the checkout URL."""
    tier = get_tier(tier_code)
    if tier is None:
        raise ValueError(f"未知方案：{tier_code}")
    if not tier["is_available"]:
        raise ValueError(
            f"方案「{tier['display_name']}」尚未開放，敬請期待。"
        )

    price_id = tier["stripe_price_id"]
    if not price_id:
        raise ValueError(
            f"方案「{tier['display_name']}」尚未設定 Stripe price_id，"
            "請先在後台管理系統填入。"
        )

    client = _get_stripe_client()
    session = client.v1.checkout.sessions.create(
        params={
            "mode": "subscription",
            "payment_method_types": ["card"],
            "line_items": [{"price": price_id, "quantity": 1}],
            "customer_email": user_email or None,
            "metadata": {"user_id": user_id, "tier_code": tier_code},
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
    )
    return session.url


# ---------------------------------------------------------------------------
# Customer Portal
# ---------------------------------------------------------------------------

def create_portal_session(*, user_id: str, return_url: str) -> str:
    """Create a Stripe Customer Portal session URL."""
    sub = get_user_subscription(user_id)
    if not sub or not sub.get("stripe_customer_id"):
        raise ValueError("找不到有效的 Stripe 客戶資料，請先完成訂閱。")

    client = _get_stripe_client()
    portal = client.v1.billing_portal.sessions.create(
        params={
            "customer": sub["stripe_customer_id"],
            "return_url": return_url,
        }
    )
    return portal.url


# ---------------------------------------------------------------------------
# Webhook signature verification
# ---------------------------------------------------------------------------

def construct_webhook_event(payload: bytes, sig_header: str) -> Any:
    """Verify Stripe-Signature header and return the parsed Event.

    Uses the module-level stripe.Webhook (not StripeClient) as required
    by the Stripe Python SDK.  payload must be the raw request bytes —
    never pass a decoded/re-serialised body.
    """
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if not webhook_secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET 未設定")
    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)


# ---------------------------------------------------------------------------
# Webhook event handlers (called from the /webhook route)
# ---------------------------------------------------------------------------

def handle_checkout_completed(event_data: Dict[str, Any]) -> None:
    """checkout.session.completed — activate the subscription."""
    session = event_data["object"]
    metadata = session.get("metadata") or {}
    user_id = metadata.get("user_id")
    tier_code = metadata.get("tier_code")

    if not user_id or not tier_code:
        logger.error(
            "[Webhook] checkout.session.completed 缺少 metadata: %s", metadata
        )
        return

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    period_end = None
    if subscription_id:
        try:
            client = _get_stripe_client()
            stripe_sub = client.v1.subscriptions.retrieve(subscription_id)
            ts = getattr(stripe_sub, "current_period_end", None)
            if ts:
                period_end = datetime.utcfromtimestamp(ts)
        except Exception as exc:
            logger.warning("[Webhook] 無法取得訂閱期限: %s", exc)

    with get_db() as db:
        _upsert_subscription(
            db,
            user_id=user_id,
            tier_code=tier_code,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            status="active",
            current_period_end=period_end,
        )
    logger.info("[Webhook] 用戶 %s 訂閱 %s 已啟用", user_id, tier_code)


def handle_subscription_updated(event_data: Dict[str, Any]) -> None:
    """customer.subscription.updated — sync status and period_end."""
    stripe_sub = event_data["object"]
    subscription_id = stripe_sub.get("id")
    if not subscription_id:
        return

    with get_db() as db:
        row = db.execute(
            select(UserSubscription).where(
                UserSubscription.stripe_subscription_id == subscription_id
            )
        ).scalar_one_or_none()
        if row is None:
            logger.warning(
                "[Webhook] subscription.updated 找不到訂閱 %s", subscription_id
            )
            return

        status = stripe_sub.get("status", row.status)
        ts = stripe_sub.get("current_period_end")
        period_end = (
            datetime.utcfromtimestamp(ts) if ts else row.current_period_end
        )
        row.status = status
        row.current_period_end = period_end
        row.touch()
    logger.info("[Webhook] 訂閱 %s 狀態更新為 %s", subscription_id, status)


def handle_subscription_deleted(event_data: Dict[str, Any]) -> None:
    """customer.subscription.deleted — mark as canceled."""
    stripe_sub = event_data["object"]
    subscription_id = stripe_sub.get("id")
    if not subscription_id:
        return

    with get_db() as db:
        row = db.execute(
            select(UserSubscription).where(
                UserSubscription.stripe_subscription_id == subscription_id
            )
        ).scalar_one_or_none()
        if row:
            row.status = "canceled"
            row.touch()
    logger.info("[Webhook] 訂閱 %s 已取消", subscription_id)


def handle_invoice_payment_failed(event_data: Dict[str, Any]) -> None:
    """invoice.payment_failed — mark subscription as past_due."""
    invoice = event_data["object"]
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return

    with get_db() as db:
        row = db.execute(
            select(UserSubscription).where(
                UserSubscription.stripe_subscription_id == subscription_id
            )
        ).scalar_one_or_none()
        if row:
            row.status = "past_due"
            row.touch()
    logger.info("[Webhook] 訂閱 %s 付款失敗，標記為 past_due", subscription_id)
