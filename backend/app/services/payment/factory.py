"""
Payment gateway factory.

Reads the `payment.gateway` setting (DB-first / env-fallback, via
payment_settings_service) and returns the matching PaymentGateway instance.
Only "stripe" is wired up today — PayUni/Shopline raise a clear error until
a later phase implements them.
"""

from .. import payment_settings_service as pay_settings
from .stripe_gateway import StripeGateway
from .types import PaymentGateway

_RESERVED_NOT_IMPLEMENTED = frozenset({"payuni", "shopline"})


def get_gateway_by_type(gateway_type: str) -> PaymentGateway:
    """Build a gateway instance for an explicit type (e.g. replaying an old webhook)."""
    gateway_type = (gateway_type or "").strip().lower()

    if gateway_type == "stripe":
        return StripeGateway(
            secret_key=pay_settings.get_stripe_secret_key() or "",
            webhook_secret=pay_settings.get_stripe_webhook_secret() or "",
            publishable_key=pay_settings.get_stripe_publishable_key(),
        )

    if gateway_type in _RESERVED_NOT_IMPLEMENTED:
        raise RuntimeError(f"金流閘道「{gateway_type}」尚未支援，敬請期待。")

    raise RuntimeError(f"未知的金流閘道：{gateway_type}")


def get_active_gateway() -> PaymentGateway:
    """Build the gateway currently selected by the `payment.gateway` setting."""
    return get_gateway_by_type(pay_settings.get_active_gateway_type())
