"""
Platform models — LLM APIs provided by the site operator (managed in /admin).

Premium/Pro subscribers (and admins) may run simulations on these without
bringing their own API key; they can still choose to use their own key instead.
API keys are Fernet-encrypted at rest (same scheme as the Stripe settings) and
are never returned by any function here except get_credentials(), which is only
meant for the LLM-resolution path in UserManager.get_llm_config().
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update

from ..db.database import get_db
from ..db.models import PlatformModel, User
from ..models.user import LLM_PROVIDER_DEFAULTS
from ..utils.logger import get_logger
from . import payment_settings_service as _secrets

logger = get_logger("futuresreport.platform_models")

# Subscription tiers that unlock platform-provided models.
PLATFORM_MODEL_TIERS = frozenset({"premium", "pro"})


# ---------------------------------------------------------------------------
# Entitlement
# ---------------------------------------------------------------------------

def user_can_use_platform_models(user: Optional[Dict[str, Any]]) -> bool:
    """`user` is the dict returned by UserManager (needs role + subscription)."""
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    sub = user.get("subscription")
    if not sub:
        return False
    return (
        sub.get("status") in ("active", "trialing")
        and sub.get("tier_code") in PLATFORM_MODEL_TIERS
    )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def _hint(api_key: str) -> str:
    key = api_key.strip()
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def _provider_label(provider: str) -> str:
    return LLM_PROVIDER_DEFAULTS.get(provider, {}).get("label", provider)


def _admin_dict(row: PlatformModel) -> Dict[str, Any]:
    return {
        "id": row.id,
        "provider": row.provider,
        "provider_label": _provider_label(row.provider),
        "model": row.model,
        "label": row.label or row.model,
        "base_url": row.base_url,
        "api_key_hint": row.api_key_hint,
        "is_enabled": row.is_enabled,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
    }


def _public_dict(row: PlatformModel) -> Dict[str, Any]:
    """What a subscriber may see — no base_url, no key material."""
    return {
        "id": row.id,
        "provider": row.provider,
        "provider_label": _provider_label(row.provider),
        "model": row.model,
        "label": row.label or row.model,
    }


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def list_models() -> List[Dict[str, Any]]:
    """All platform models (admin view)."""
    with get_db() as db:
        rows = db.execute(
            select(PlatformModel).order_by(PlatformModel.id)
        ).scalars().all()
        return [_admin_dict(r) for r in rows]


def list_public_models() -> List[Dict[str, Any]]:
    """Enabled platform models, safe to show to entitled subscribers."""
    with get_db() as db:
        rows = db.execute(
            select(PlatformModel)
            .where(PlatformModel.is_enabled.is_(True))
            .order_by(PlatformModel.id)
        ).scalars().all()
        return [_public_dict(r) for r in rows]


def get_public_model(model_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """Enabled model by id, or None (missing / disabled / dangling id)."""
    if not model_id:
        return None
    with get_db() as db:
        row = db.get(PlatformModel, model_id)
        if row is None or not row.is_enabled:
            return None
        return _public_dict(row)


def get_credentials(model_id: Optional[int]) -> Optional[Dict[str, str]]:
    """Decrypted llm_config-shaped dict for an enabled model, else None."""
    if not model_id:
        return None
    with get_db() as db:
        row = db.get(PlatformModel, model_id)
        if row is None or not row.is_enabled:
            return None
        api_key = _secrets.decrypt_secret(row.api_key_cipher)
        if not api_key:
            return None
        return {
            "provider": row.provider,
            "model": row.model,
            "base_url": row.base_url,
            "api_key": api_key,
        }


# ---------------------------------------------------------------------------
# Write (admin)
# ---------------------------------------------------------------------------

def _clean_provider(provider: str) -> str:
    provider = (provider or "").strip().lower()
    if provider not in LLM_PROVIDER_DEFAULTS:
        raise ValueError("不支援的模型供應商。")
    return provider


def create_model(
    *,
    provider: str,
    model: str,
    api_key: str,
    label: str = "",
    base_url: str = "",
    is_enabled: bool = True,
) -> Dict[str, Any]:
    provider = _clean_provider(provider)
    defaults = LLM_PROVIDER_DEFAULTS[provider]
    model = (model or defaults["default_model"]).strip()
    api_key = (api_key or "").strip()
    if not api_key:
        raise ValueError("請輸入 API 金鑰。")
    base_url = (base_url or defaults["base_url"]).strip().rstrip("/")

    now = datetime.utcnow()
    with get_db() as db:
        row = PlatformModel(
            provider=provider,
            model=model,
            label=(label or "").strip(),
            base_url=base_url,
            api_key_cipher=_secrets.encrypt_secret(api_key),
            api_key_hint=_hint(api_key),
            is_enabled=bool(is_enabled),
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.flush()
        return _admin_dict(row)


def update_model(model_id: int, **fields: Any) -> Dict[str, Any]:
    """Partial update. `api_key` is only replaced when a non-empty value is given."""
    with get_db() as db:
        row = db.get(PlatformModel, model_id)
        if row is None:
            raise LookupError("找不到此平台模型。")

        if "provider" in fields:
            row.provider = _clean_provider(fields["provider"])
        if "model" in fields:
            value = (fields["model"] or "").strip()
            if not value:
                raise ValueError("模型名稱不可為空。")
            row.model = value
        if "label" in fields:
            row.label = (fields["label"] or "").strip()
        if "base_url" in fields:
            value = (fields["base_url"] or "").strip().rstrip("/")
            if not value:
                raise ValueError("Base URL 不可為空。")
            row.base_url = value
        if "is_enabled" in fields:
            row.is_enabled = bool(fields["is_enabled"])
        api_key = (fields.get("api_key") or "").strip()
        if api_key:
            row.api_key_cipher = _secrets.encrypt_secret(api_key)
            row.api_key_hint = _hint(api_key)

        row.updated_at = datetime.utcnow()
        db.flush()
        return _admin_dict(row)


def delete_model(model_id: int) -> None:
    with get_db() as db:
        row = db.get(PlatformModel, model_id)
        if row is None:
            raise LookupError("找不到此平台模型。")
        # Users who had selected it fall back to their own API.
        db.execute(
            update(User)
            .where(User.platform_model_id == model_id)
            .values(platform_model_id=None)
        )
        db.delete(row)
