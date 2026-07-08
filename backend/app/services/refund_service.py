"""
Admin-initiated refund + immediate subscription cancellation.

Mirrors shineyang's markAsRefunded three-line-of-defence pattern
(lib/actions/orders.ts, ~L375-460):

  1. Atomic compare-and-swap claim (active/trialing/past_due -> refunding)
     so a double-click or a concurrent request can only ever refund once.
  2. Gateway refund; the claim is rolled back if the gateway call fails.
  3. Gateway subscription cancellation (best effort) — the refund has
     already succeeded at this point, so a cancel failure is logged and
     surfaced as requires_manual_action instead of being rolled back.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy import update as sa_update

from ..db.database import get_db
from ..db.models import RefundRecord, UserSubscription
from ..utils.logger import get_logger
from . import subscription_service as sub_svc
from .payment import factory as payment_factory

logger = get_logger("futuresreport.refund")

_CLAIMABLE_STATUSES = ("active", "trialing", "past_due")


class RefundConflictError(Exception):
    """The atomic claim failed — subscription status changed concurrently."""


class RefundGatewayError(Exception):
    """The payment gateway rejected the refund. The claim has been rolled back."""


# ---------------------------------------------------------------------------
# Atomic claim / rollback (line of defence #1)
# ---------------------------------------------------------------------------

def claim_subscription_for_refund(user_id: str) -> Optional[str]:
    """Atomically flip active/trialing/past_due -> refunding.

    Returns the previous status on success (needed for rollback), or None if
    the claim failed — no subscription, or status already changed (already
    refunding/canceled, or a concurrent request won the race).
    """
    with get_db() as db:
        row = db.execute(
            select(UserSubscription).where(UserSubscription.user_id == user_id)
        ).scalar_one_or_none()
        if row is None or row.status not in _CLAIMABLE_STATUSES:
            return None

        previous_status = row.status
        result = db.execute(
            sa_update(UserSubscription)
            .where(
                UserSubscription.user_id == user_id,
                UserSubscription.status == previous_status,
            )
            .values(status="refunding", updated_at=datetime.utcnow())
        )
        if result.rowcount == 0:
            return None

    return previous_status


def rollback_refund_claim(user_id: str, previous_status: str) -> None:
    with get_db() as db:
        row = db.execute(
            select(UserSubscription).where(UserSubscription.user_id == user_id)
        ).scalar_one_or_none()
        if row is not None and row.status == "refunding":
            row.status = previous_status
            row.touch()


def _finalize_refund(
    *,
    user_id: str,
    stripe_subscription_id: str,
    stripe_payment_intent_id: str,
    stripe_refund_id: Optional[str],
    amount: Optional[int],
    currency: Optional[str],
    reason: str,
    admin_user_id: str,
) -> None:
    with get_db() as db:
        row = db.execute(
            select(UserSubscription).where(UserSubscription.user_id == user_id)
        ).scalar_one_or_none()
        if row is not None:
            row.status = "canceled"
            row.touch()

        db.add(RefundRecord(
            user_id=user_id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_payment_intent_id=stripe_payment_intent_id,
            stripe_refund_id=stripe_refund_id,
            amount=amount,
            currency=currency,
            reason=reason,
            admin_user_id=admin_user_id,
            created_at=datetime.utcnow(),
        ))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def refund_user_subscription(
    *, user_id: str, reason: str, admin_user_id: str
) -> Dict[str, Any]:
    """Refund the most recent invoice and immediately cancel the subscription.

    Raises:
        ValueError            — no Stripe-backed subscription (admin manually
                                 granted the tier; there is nothing to refund online)
        RefundConflictError   — atomic claim failed (concurrent request / stale state)
        RefundGatewayError    — the gateway rejected the refund; claim rolled back
    """
    sub = sub_svc.get_user_subscription(user_id)
    subscription_id = sub.get("stripe_subscription_id") if sub else None
    if not subscription_id:
        raise ValueError("此訂閱非經 Stripe 建立，無法線上退款")

    previous_status = claim_subscription_for_refund(user_id)
    if previous_status is None:
        raise RefundConflictError("狀態已變更，請重新整理")

    gateway = payment_factory.get_active_gateway()

    try:
        payment_intent_id, invoice_id = gateway.get_latest_invoice_payment_intent(subscription_id)
        if not payment_intent_id:
            raise RefundGatewayError("找不到可退款的付款紀錄")

        refund_result = gateway.process_refund(
            payment_intent_id=payment_intent_id,
            idempotency_key=f"refund_{invoice_id}",
        )
        if not refund_result.success:
            raise RefundGatewayError(refund_result.error or "金流退款失敗")
    except RefundGatewayError:
        rollback_refund_claim(user_id, previous_status)
        raise
    except Exception as exc:
        rollback_refund_claim(user_id, previous_status)
        raise RefundGatewayError(str(exc)) from exc

    requires_manual_action = False
    try:
        gateway.cancel_subscription(subscription_id)
    except Exception as exc:
        requires_manual_action = True
        logger.error(
            "[Refund] 退款已成功但取消訂閱失敗，需人工至 Stripe Dashboard 處理："
            "user=%s sub=%s err=%s",
            user_id, subscription_id, exc,
        )

    _finalize_refund(
        user_id=user_id,
        stripe_subscription_id=subscription_id,
        stripe_payment_intent_id=payment_intent_id,
        stripe_refund_id=refund_result.refund_id,
        amount=refund_result.amount,
        currency=refund_result.currency,
        reason=reason,
        admin_user_id=admin_user_id,
    )

    logger.info(
        "[Refund] 用戶 %s 訂閱 %s 已退款並取消 (admin=%s)",
        user_id, subscription_id, admin_user_id,
    )

    return {
        "refund_id": refund_result.refund_id,
        "requires_manual_action": requires_manual_action,
    }
