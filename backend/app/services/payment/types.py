"""
Payment gateway abstract interface.

Every payment gateway (Stripe today; PayUni/Shopline reserved for later)
implements this ABC. subscription_service.py and the admin API only ever
talk to a PaymentGateway instance obtained from payment.factory — they
never import the `stripe` SDK directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class CheckoutSessionParams:
    user_id: str
    user_email: Optional[str]
    tier_code: str
    price_id: str
    success_url: str
    cancel_url: str


@dataclass
class PortalSessionParams:
    customer_id: str
    return_url: str


@dataclass
class RefundResult:
    success: bool
    refund_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class SettingsSummary:
    is_configured: bool
    secret_key_hint: Optional[str]
    publishable_key_hint: Optional[str]
    is_test_mode: bool
    webhook_configured: bool
    webhook_url: str


class PaymentGateway(ABC):
    """Unified interface every payment gateway must implement."""

    @property
    @abstractmethod
    def gateway_type(self) -> str:
        """Machine-readable gateway id, e.g. "stripe"."""

    @property
    @abstractmethod
    def supports_recurring(self) -> bool:
        """Whether this gateway supports subscription billing."""

    @abstractmethod
    def create_checkout_session(self, params: CheckoutSessionParams) -> str:
        """Create a checkout session and return its redirect URL."""

    @abstractmethod
    def create_portal_session(self, params: PortalSessionParams) -> str:
        """Create a billing-management portal session and return its URL."""

    @abstractmethod
    def process_refund(
        self, *, payment_intent_id: str, idempotency_key: str
    ) -> RefundResult:
        """Refund the payment behind payment_intent_id."""

    @abstractmethod
    def cancel_subscription(self, subscription_id: str) -> None:
        """Cancel a subscription immediately (not at period end)."""

    @abstractmethod
    def test_connection(self) -> "tuple[bool, str]":
        """Verify the configured credentials actually work."""

    @abstractmethod
    def get_settings_summary(self, base_url: str) -> SettingsSummary:
        """Masked configuration snapshot for the admin UI."""

    @abstractmethod
    def construct_webhook_event(self, payload: bytes, sig_header: str) -> Any:
        """Verify + parse an inbound webhook payload."""

    @abstractmethod
    def get_subscription_period_end(self, subscription_id: str) -> Optional[datetime]:
        """Return the current billing period's end date for a subscription.

        Not part of the shineyang reference interface, but required so that
        subscription_service's webhook handlers never touch the gateway SDK
        directly (see checkout.session.completed handling).
        """
