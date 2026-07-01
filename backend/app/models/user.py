"""
Account and per-user LLM credential storage – SQLAlchemy backend.

Public API is identical to the previous JSON-file implementation so that
all Flask route handlers work without modification.
"""

import base64
import hashlib
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, select
from werkzeug.security import check_password_hash, generate_password_hash

from ..config import Config
from ..db.database import get_db
from ..db.models import LlmConfig, User


# ---------------------------------------------------------------------------
# LLM provider catalogue
# ---------------------------------------------------------------------------

LLM_PROVIDER_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": [
            "gpt-4o-mini", "gpt-4o",
            "gpt-4.1-mini", "gpt-4.1",
            "o4-mini", "o3-mini", "o3",
        ],
        "default_model": "gpt-4o-mini",
    },
    "anthropic": {
        "label": "Claude / Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "models": [
            "claude-opus-4-8",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-opus-latest",
        ],
        "default_model": "claude-sonnet-4-6",
    },
    "qwen": {
        "label": "Qwen / DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            "qwen-plus", "qwen-max", "qwen-turbo",
            "qwen3-235b-a22b", "qwen3-30b-a3b", "qwen-long",
        ],
        "default_model": "qwen-plus",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": [
            "deepseek-v4-pro",
            "deepseek-v4-flash",
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        "default_model": "deepseek-v4-pro",
    },
    "kimi": {
        "label": "Kimi / Moonshot AI",
        "base_url": "https://api.moonshot.cn/v1",
        "models": [
            "kimi-k2-0711-preview",
            "kimi-k2-6-preview",
            "moonshot-v1-128k",
            "moonshot-v1-32k",
            "moonshot-v1-8k",
        ],
        "default_model": "kimi-k2-0711-preview",
    },
    "glm": {
        "label": "GLM / Zhipu AI",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": [
            "glm-4-plus", "glm-4-air", "glm-4-flash",
            "glm-z1-plus", "glm-z1-air", "glm-z1-flash",
        ],
        "default_model": "glm-4-plus",
    },
    "minimax": {
        "label": "MiniMax",
        "base_url": "https://api.minimaxi.chat/v1",
        "models": [
            "minimax-m3",
            "minimax-m2.7",
        ],
        "default_model": "minimax-m3",
    },
    "nvidia": {
        "label": "NVIDIA NIM (Nemotron)",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "models": [
            "nvidia/nemotron-4-340b-instruct",
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "nvidia/llama-3.1-nemotron-nano-8b-v1",
            "nvidia/nemotron-mini-4b-instruct",
        ],
        "default_model": "nvidia/nemotron-4-340b-instruct",
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": [
            "gemini-3.5-flash",
            "gemini-3.1-pro",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ],
        "default_model": "gemini-2.5-flash",
    },
    "mistral": {
        "label": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "models": [
            "mistral-large-latest",
            "mistral-small-latest",
            "mistral-nemo",
            "open-mixtral-8x22b",
            "open-mixtral-8x7b",
            "codestral-latest",
        ],
        "default_model": "mistral-large-latest",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dt(dt: Optional[datetime]) -> Optional[str]:
    """Convert a datetime to an ISO-8601 string with Z suffix."""
    if dt is None:
        return None
    return dt.isoformat() + "Z"


def _orm_to_dict(user: User) -> Dict[str, Any]:
    """Convert a SQLAlchemy User row to the canonical dict format."""
    llm = user.llm_config
    sub = user.subscription
    return {
        "user_id": user.user_id,
        "username": user.username,
        "password_hash": user.password_hash,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": _dt(user.created_at),
        "updated_at": _dt(user.updated_at),
        "llm_config": {
            "provider": llm.provider,
            "model": llm.model,
            "base_url": llm.base_url,
            "api_key_cipher": llm.api_key_cipher,
            "api_key_hint": llm.api_key_hint,
            "updated_at": _dt(llm.updated_at),
        } if llm else None,
        "subscription": {
            "tier_code": sub.tier_code,
            "status": sub.status,
            "stripe_subscription_id": sub.stripe_subscription_id,
            "stripe_customer_id": sub.stripe_customer_id,
        } if sub else None,
    }


# ---------------------------------------------------------------------------
# UserManager
# ---------------------------------------------------------------------------

class UserManager:
    """
    All public methods return plain dicts (same contract as the old JSON
    implementation) so Flask route handlers need zero changes.
    """

    _serializer: Optional[URLSafeTimedSerializer] = None

    # ------------------------------------------------------------------
    # Token helpers (unchanged – itsdangerous)
    # ------------------------------------------------------------------

    @classmethod
    def _serializer_instance(cls) -> URLSafeTimedSerializer:
        if cls._serializer is None:
            cls._serializer = URLSafeTimedSerializer(
                Config.SECRET_KEY, salt="futures-report-auth"
            )
        return cls._serializer

    @classmethod
    def issue_token(cls, user_id: str) -> str:
        return cls._serializer_instance().dumps({"user_id": user_id})

    @classmethod
    def issue_admin_token(cls, user_id: str) -> str:
        return cls._serializer_instance().dumps({"role": "admin", "user_id": user_id})

    @classmethod
    def verify_token(
        cls, token: str, max_age: int = 60 * 60 * 24 * 30
    ) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        try:
            payload = cls._serializer_instance().loads(token, max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None
        return cls.get_user(payload.get("user_id"))

    @classmethod
    def verify_admin_token(
        cls, token: str, max_age: int = 60 * 60 * 8
    ) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        try:
            payload = cls._serializer_instance().loads(token, max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None
        if payload.get("role") != "admin":
            return None
        user = cls.get_user(payload.get("user_id", ""))
        if not user or user.get("role") != "admin":
            return None
        return {
            "role": "admin",
            "user_id": user["user_id"],
            "username": user.get("username", ""),
        }

    # ------------------------------------------------------------------
    # Encryption helpers (unchanged – XOR + SHA-256 stream)
    # ------------------------------------------------------------------

    @classmethod
    def _secret_stream(cls, length: int) -> bytes:
        secret = Config.SECRET_KEY.encode("utf-8")
        output = bytearray()
        counter = 0
        while len(output) < length:
            output.extend(
                hashlib.sha256(secret + counter.to_bytes(8, "big")).digest()
            )
            counter += 1
        return bytes(output[:length])

    @classmethod
    def _protect_secret(cls, secret: str) -> str:
        data = secret.encode("utf-8")
        stream = cls._secret_stream(len(data))
        encrypted = bytes(a ^ b for a, b in zip(data, stream))
        return base64.urlsafe_b64encode(encrypted).decode("ascii")

    @classmethod
    def _unprotect_secret(cls, protected: str) -> str:
        encrypted = base64.urlsafe_b64decode(protected.encode("ascii"))
        stream = cls._secret_stream(len(encrypted))
        data = bytes(a ^ b for a, b in zip(encrypted, stream))
        return data.decode("utf-8")

    @classmethod
    def _api_key_hint(cls, api_key: Optional[str]) -> str:
        if not api_key:
            return ""
        key = api_key.strip()
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"

    # ------------------------------------------------------------------
    # Provider catalogue
    # ------------------------------------------------------------------

    @classmethod
    def providers(cls) -> Dict[str, Dict[str, Any]]:
        return deepcopy(LLM_PROVIDER_DEFAULTS)

    # ------------------------------------------------------------------
    # Public representation (dict → dict, no ORM exposure)
    # ------------------------------------------------------------------

    @classmethod
    def public_user(cls, user: Dict[str, Any]) -> Dict[str, Any]:
        llm_config = user.get("llm_config") or {}
        sub = user.get("subscription")
        return {
            "user_id": user.get("user_id"),
            "username": user.get("username"),
            "role": user.get("role", "user"),
            "is_admin": user.get("role") == "admin",
            "is_active": user.get("is_active", True),
            "created_at": user.get("created_at"),
            "llm_configured": bool(llm_config.get("api_key_cipher")),
            "llm": {
                "provider": llm_config.get("provider"),
                "model": llm_config.get("model"),
                "base_url": llm_config.get("base_url"),
                "api_key_hint": llm_config.get("api_key_hint"),
                "updated_at": llm_config.get("updated_at"),
            } if llm_config else None,
            "subscription": sub,
        }

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @classmethod
    def create_user(cls, username: str, password: str) -> Dict[str, Any]:
        username = (username or "").strip()
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if len(password or "") < 8:
            raise ValueError("Password must be at least 8 characters.")

        with get_db() as db:
            existing = db.execute(
                select(User).where(
                    func.lower(User.username) == username.lower()
                )
            ).scalar_one_or_none()
            if existing:
                raise ValueError("Username already exists.")

            count = db.execute(
                select(func.count()).select_from(User)
            ).scalar_one()

            now = datetime.utcnow()
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                role="admin" if count == 0 else "user",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(user)
            db.flush()  # populate user.user_id before _orm_to_dict
            result = _orm_to_dict(user)

        return result

    @classmethod
    def authenticate(
        cls, username: str, password: str
    ) -> Optional[Dict[str, Any]]:
        user_dict = cls.get_user_by_username(username)
        if not user_dict:
            return None
        if not user_dict.get("is_active", True):
            return None
        if check_password_hash(user_dict["password_hash"], password or ""):
            return user_dict
        return None

    @classmethod
    def get_user_by_username(cls, username: str) -> Optional[Dict[str, Any]]:
        username = (username or "").strip().lower()
        with get_db() as db:
            row = db.execute(
                select(User).where(func.lower(User.username) == username)
            ).scalar_one_or_none()
            if row is None:
                return None
            return _orm_to_dict(row)

    @classmethod
    def get_user(cls, user_id: str) -> Optional[Dict[str, Any]]:
        if not user_id:
            return None
        with get_db() as db:
            row = db.execute(
                select(User).where(User.user_id == user_id)
            ).scalar_one_or_none()
            if row is None:
                return None
            return _orm_to_dict(row)

    @classmethod
    def list_public_users(cls) -> List[Dict[str, Any]]:
        with get_db() as db:
            rows = db.execute(
                select(User).order_by(User.created_at)
            ).scalars().all()
            return [cls.public_user(_orm_to_dict(r)) for r in rows]

    @classmethod
    def update_user(
        cls,
        user_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        with get_db() as db:
            user = db.execute(
                select(User).where(User.user_id == user_id)
            ).scalar_one_or_none()
            if not user:
                raise ValueError("User not found.")

            if username is not None:
                username = username.strip()
                if len(username) < 3:
                    raise ValueError("Username must be at least 3 characters.")
                conflict = db.execute(
                    select(User).where(
                        func.lower(User.username) == username.lower(),
                        User.user_id != user_id,
                    )
                ).scalar_one_or_none()
                if conflict:
                    raise ValueError("Username already exists.")
                user.username = username

            if password:
                if len(password) < 8:
                    raise ValueError("Password must be at least 8 characters.")
                user.password_hash = generate_password_hash(password)

            if role is not None:
                if role not in ("admin", "user"):
                    raise ValueError("Role must be 'admin' or 'user'.")
                # Guard: cannot demote the last admin
                if role == "user" and user.role == "admin":
                    admin_count = db.execute(
                        select(func.count()).select_from(User).where(
                            User.role == "admin"
                        )
                    ).scalar_one()
                    if admin_count <= 1:
                        raise ValueError("Cannot demote the last administrator.")
                user.role = role

            if is_active is not None:
                user.is_active = is_active

            if llm_config is not None:
                if llm_config.get("clear"):
                    if user.llm_config:
                        db.delete(user.llm_config)
                        user.llm_config = None
                elif (provider := (llm_config.get("provider") or "").strip().lower()):
                    if provider not in LLM_PROVIDER_DEFAULTS:
                        raise ValueError("Unsupported LLM provider.")
                    defaults = LLM_PROVIDER_DEFAULTS[provider]
                    api_key = (llm_config.get("api_key") or "").strip()

                    if user.llm_config:
                        cfg = user.llm_config
                    else:
                        cfg = LlmConfig(user_id=user.user_id)
                        db.add(cfg)
                        user.llm_config = cfg

                    cfg.provider = provider
                    cfg.model = (
                        llm_config.get("model") or defaults["default_model"]
                    ).strip()
                    cfg.base_url = (
                        llm_config.get("base_url") or defaults["base_url"]
                    ).strip().rstrip("/")
                    if api_key:
                        cfg.api_key_cipher = cls._protect_secret(api_key)
                        cfg.api_key_hint = cls._api_key_hint(api_key)
                    cfg.updated_at = datetime.utcnow()

            user.touch()
            db.flush()
            result = _orm_to_dict(user)

        return result

    @classmethod
    def set_llm_config(
        cls,
        user_id: str,
        provider: str,
        model: str,
        api_key: Optional[str],
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        provider = (provider or "").strip().lower()
        if provider not in LLM_PROVIDER_DEFAULTS:
            raise ValueError("Unsupported LLM provider.")

        provider_defaults = LLM_PROVIDER_DEFAULTS[provider]
        model = (model or provider_defaults["default_model"]).strip()
        base_url = (base_url or provider_defaults["base_url"]).strip().rstrip("/")

        with get_db() as db:
            user = db.execute(
                select(User).where(User.user_id == user_id)
            ).scalar_one_or_none()
            if not user:
                raise ValueError("User not found.")

            existing_cipher = user.llm_config.api_key_cipher if user.llm_config else None
            if api_key:
                new_cipher = cls._protect_secret(api_key.strip())
                new_hint = cls._api_key_hint(api_key)
            elif existing_cipher:
                new_cipher = existing_cipher
                new_hint = user.llm_config.api_key_hint if user.llm_config else ""
            else:
                raise ValueError("API key is required.")

            if user.llm_config:
                cfg = user.llm_config
            else:
                cfg = LlmConfig(user_id=user_id)
                db.add(cfg)
                user.llm_config = cfg

            cfg.provider = provider
            cfg.model = model
            cfg.base_url = base_url
            cfg.api_key_cipher = new_cipher
            cfg.api_key_hint = new_hint
            cfg.updated_at = datetime.utcnow()
            user.touch()
            db.flush()
            result = _orm_to_dict(user)

        return result

    @classmethod
    def get_llm_config(cls, user_id: str) -> Optional[Dict[str, str]]:
        user = cls.get_user(user_id)
        if not user:
            return None
        cfg = user.get("llm_config")
        if not cfg or not cfg.get("api_key_cipher"):
            return None
        return {
            "provider": cfg.get("provider", "openai"),
            "model": cfg.get("model") or LLM_PROVIDER_DEFAULTS["openai"]["default_model"],
            "base_url": cfg.get("base_url") or LLM_PROVIDER_DEFAULTS["openai"]["base_url"],
            "api_key": cls._unprotect_secret(cfg["api_key_cipher"]),
        }

    @classmethod
    def delete_user(cls, user_id: str) -> None:
        with get_db() as db:
            user = db.execute(
                select(User).where(User.user_id == user_id)
            ).scalar_one_or_none()
            if not user:
                raise ValueError("User not found.")
            if user.role == "admin":
                admin_count = db.execute(
                    select(func.count()).select_from(User).where(User.role == "admin")
                ).scalar_one()
                if admin_count <= 1:
                    raise ValueError("Cannot delete the last administrator.")
            db.delete(user)

    @classmethod
    def set_user_subscription(
        cls, user_id: str, tier_code: Optional[str]
    ) -> Dict[str, Any]:
        """Admin override: grant or revoke a subscription tier without Stripe."""
        from ..db.models import UserSubscription, SubscriptionTier

        with get_db() as db:
            user = db.execute(
                select(User).where(User.user_id == user_id)
            ).scalar_one_or_none()
            if not user:
                raise ValueError("User not found.")

            if not tier_code:
                if user.subscription:
                    db.delete(user.subscription)
                    user.subscription = None
            else:
                tier = db.execute(
                    select(SubscriptionTier).where(
                        SubscriptionTier.tier_code == tier_code
                    )
                ).scalar_one_or_none()
                if tier is None:
                    raise ValueError(f"未知方案代碼：{tier_code}")

                now = datetime.utcnow()
                if user.subscription:
                    user.subscription.tier_code = tier_code
                    user.subscription.status = "active"
                    user.subscription.updated_at = now
                else:
                    new_sub = UserSubscription(
                        user_id=user_id,
                        tier_code=tier_code,
                        status="active",
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(new_sub)
                    user.subscription = new_sub

            db.flush()
            result = _orm_to_dict(user)

        return result

    @classmethod
    def get_stats(cls) -> Dict[str, int]:
        with get_db() as db:
            total = db.execute(
                select(func.count()).select_from(User)
            ).scalar_one()
            admins = db.execute(
                select(func.count()).select_from(User).where(User.role == "admin")
            ).scalar_one()
            active = db.execute(
                select(func.count()).select_from(User).where(User.is_active == True)  # noqa: E712
            ).scalar_one()
            llm_configured = db.execute(
                select(func.count()).select_from(LlmConfig)
            ).scalar_one()
        return {
            "total_users": total,
            "admin_users": admins,
            "active_users": active,
            "llm_configured": llm_configured,
        }
