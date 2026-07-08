"""
Stripe payment gateway — implements the PaymentGateway ABC.

Every direct Stripe SDK call in the app lives here. subscription_service.py
and the admin API only ever go through payment.factory, never `import stripe`
themselves.
"""

from datetime import datetime
from typing import Optional

import stripe

from ...utils.logger import get_logger
from .types import (
    CheckoutSessionParams,
    PaymentGateway,
    PortalSessionParams,
    RefundResult,
    SettingsSummary,
)

logger = get_logger("futuresreport.payment.stripe")


class StripeGateway(PaymentGateway):
    gateway_type = "stripe"
    supports_recurring = True

    def __init__(
        self,
        *,
        secret_key: str,
        webhook_secret: str = "",
        publishable_key: Optional[str] = None,
    ):
        if not secret_key:
            raise RuntimeError(
                "STRIPE_SECRET_KEY 未設定。請在後台「金流設定」或 .env / Zeabur 環境變數中填入。"
            )
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret
        self._publishable_key = publishable_key
        self._client = stripe.StripeClient(secret_key)

    # -----------------------------------------------------------------
    # Checkout / portal
    # -----------------------------------------------------------------

    def create_checkout_session(self, params: CheckoutSessionParams) -> str:
        session = self._client.v1.checkout.sessions.create(
            params={
                "mode": "subscription",
                "payment_method_types": ["card"],
                "line_items": [{"price": params.price_id, "quantity": 1}],
                "customer_email": params.user_email or None,
                "metadata": {
                    "user_id": params.user_id,
                    "tier_code": params.tier_code,
                },
                "success_url": params.success_url,
                "cancel_url": params.cancel_url,
            }
        )
        return session.url

    def create_portal_session(self, params: PortalSessionParams) -> str:
        portal = self._client.v1.billing_portal.sessions.create(
            params={
                "customer": params.customer_id,
                "return_url": params.return_url,
            }
        )
        return portal.url

    # -----------------------------------------------------------------
    # Refund / cancel (Phase 3 admin refund flow)
    # -----------------------------------------------------------------

    def process_refund(
        self, *, payment_intent_id: str, idempotency_key: str
    ) -> RefundResult:
        try:
            refund = self._client.v1.refunds.create(
                params={"payment_intent": payment_intent_id},
                options={"idempotency_key": idempotency_key},
            )
            return RefundResult(success=True, refund_id=refund.id)
        except stripe.StripeError as exc:
            return RefundResult(success=False, error=str(exc))

    def cancel_subscription(self, subscription_id: str) -> None:
        self._client.v1.subscriptions.cancel(subscription_id)

    # -----------------------------------------------------------------
    # Diagnostics / settings
    # -----------------------------------------------------------------

    def test_connection(self) -> "tuple[bool, str]":
        try:
            balance = self._client.v1.balance.retrieve()
            is_test = self._secret_key.startswith("sk_test_")
            currencies = ", ".join(
                sorted({b.currency.upper() for b in balance.available})
            )
            return True, f"連線成功（{'測試' if is_test else '正式'}環境）。支援幣別：{currencies}"
        except stripe.StripeError as exc:
            return False, f"連線失敗：{exc}"

    def get_settings_summary(self, base_url: str) -> SettingsSummary:
        def mask(value: Optional[str]) -> Optional[str]:
            if not value:
                return None
            if len(value) <= 11:
                return f"{value[:2]}...{value[-2:]}"
            return f"{value[:7]}...{value[-4:]}"

        return SettingsSummary(
            is_configured=bool(self._secret_key) and bool(self._webhook_secret),
            secret_key_hint=mask(self._secret_key),
            publishable_key_hint=mask(self._publishable_key),
            is_test_mode=self._secret_key.startswith("sk_test_"),
            webhook_configured=bool(self._webhook_secret),
            webhook_url=f"{base_url.rstrip('/')}/api/subscription/webhook",
        )

    # -----------------------------------------------------------------
    # Webhook
    # -----------------------------------------------------------------

    def construct_webhook_event(self, payload: bytes, sig_header: str):
        if not self._webhook_secret:
            raise RuntimeError("STRIPE_WEBHOOK_SECRET 未設定")
        return stripe.Webhook.construct_event(payload, sig_header, self._webhook_secret)

    # -----------------------------------------------------------------
    # Subscription lookups
    # -----------------------------------------------------------------

    def get_subscription_period_end(self, subscription_id: str) -> Optional[datetime]:
        try:
            stripe_sub = self._client.v1.subscriptions.retrieve(subscription_id)
        except stripe.StripeError as exc:
            logger.warning("[StripeGateway] 無法取得訂閱期限: %s", exc)
            return None
        ts = getattr(stripe_sub, "current_period_end", None)
        return datetime.utcfromtimestamp(ts) if ts else None
