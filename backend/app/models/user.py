"""
Lightweight account and per-user LLM credential storage.
"""

import base64
import hashlib
import json
import os
import secrets
import shutil
import threading
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from ..config import Config


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
            "deepseek-chat",
            "deepseek-chat-v4-pro",
            "deepseek-chat-v4-flash",
            "deepseek-reasoner",
        ],
        "default_model": "deepseek-chat",
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
            "MiniMax-Text-01",
            "MiniMax-M1-40k",
            "MiniMax-M2.7",
        ],
        "default_model": "MiniMax-Text-01",
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
    "gemma": {
        "label": "Google Gemma (AI Studio)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": [
            "gemma-3-27b-it",
            "gemma-3-12b-it",
            "gemma-3-4b-it",
            "gemma-2-27b-it",
            "gemma-2-9b-it",
        ],
        "default_model": "gemma-3-27b-it",
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


class UserManager:
    _lock = threading.RLock()
    _serializer: Optional[URLSafeTimedSerializer] = None

    @classmethod
    def _storage_path(cls) -> str:
        return Config.USER_DATA_FILE

    @classmethod
    def _legacy_storage_path(cls) -> str:
        return Config.LEGACY_USER_DATA_FILE

    @classmethod
    def _ensure_storage(cls) -> None:
        path = cls._storage_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            legacy_path = cls._legacy_storage_path()
            if legacy_path != path and os.path.exists(legacy_path):
                shutil.copy2(legacy_path, path)
                return
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"users": []}, f, ensure_ascii=False, indent=2)

    @classmethod
    def _load(cls) -> Dict[str, Any]:
        cls._ensure_storage()
        with open(cls._storage_path(), "r", encoding="utf-8") as f:
            data = json.load(f)

        changed = cls._normalize_roles(data)
        if changed:
            cls._save_raw(data)
        return data

    @classmethod
    def _save(cls, data: Dict[str, Any]) -> None:
        cls._normalize_roles(data)
        cls._save_raw(data)

    @classmethod
    def _save_raw(cls, data: Dict[str, Any]) -> None:
        cls._ensure_storage()
        tmp_path = f"{cls._storage_path()}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, cls._storage_path())

    @classmethod
    def _normalize_roles(cls, data: Dict[str, Any]) -> bool:
        users = data.get("users") or []
        changed = False
        for index, user in enumerate(users):
            expected_role = "admin" if index == 0 else "user"
            if user.get("role") != expected_role:
                user["role"] = expected_role
                changed = True
        return changed

    @classmethod
    def providers(cls) -> Dict[str, Dict[str, Any]]:
        return deepcopy(LLM_PROVIDER_DEFAULTS)

    @classmethod
    def _serializer_instance(cls) -> URLSafeTimedSerializer:
        if cls._serializer is None:
            cls._serializer = URLSafeTimedSerializer(Config.SECRET_KEY, salt="futures-report-auth")
        return cls._serializer

    @classmethod
    def issue_token(cls, user_id: str) -> str:
        return cls._serializer_instance().dumps({"user_id": user_id})

    @classmethod
    def issue_admin_token(cls, user_id: str) -> str:
        return cls._serializer_instance().dumps({"role": "admin", "user_id": user_id})

    @classmethod
    def verify_admin_token(cls, token: str, max_age: int = 60 * 60 * 8) -> Optional[Dict[str, Any]]:
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
            "user_id": user.get("user_id"),
            "username": user.get("username", ""),
        }

    @classmethod
    def verify_token(cls, token: str, max_age: int = 60 * 60 * 24 * 30) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        try:
            payload = cls._serializer_instance().loads(token, max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None
        return cls.get_user(payload.get("user_id"))

    @classmethod
    def create_user(cls, username: str, password: str) -> Dict[str, Any]:
        username = (username or "").strip()
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if len(password or "") < 8:
            raise ValueError("Password must be at least 8 characters.")

        with cls._lock:
            data = cls._load()
            if any(u["username"].lower() == username.lower() for u in data["users"]):
                raise ValueError("Username already exists.")

            now = datetime.utcnow().isoformat() + "Z"
            user = {
                "user_id": f"user_{secrets.token_urlsafe(12)}",
                "username": username,
                "password_hash": generate_password_hash(password),
                "role": "admin" if len(data["users"]) == 0 else "user",
                "created_at": now,
                "updated_at": now,
                "llm_config": None,
            }
            data["users"].append(user)
            cls._save(data)
            return user

    @classmethod
    def authenticate(cls, username: str, password: str) -> Optional[Dict[str, Any]]:
        user = cls.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password or ""):
            return user
        return None

    @classmethod
    def get_user_by_username(cls, username: str) -> Optional[Dict[str, Any]]:
        username = (username or "").strip().lower()
        with cls._lock:
            data = cls._load()
            for user in data["users"]:
                if user["username"].lower() == username:
                    return deepcopy(user)
        return None

    @classmethod
    def get_user(cls, user_id: str) -> Optional[Dict[str, Any]]:
        if not user_id:
            return None
        with cls._lock:
            data = cls._load()
            for user in data["users"]:
                if user["user_id"] == user_id:
                    return deepcopy(user)
        return None

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

        with cls._lock:
            data = cls._load()
            for user in data["users"]:
                if user["user_id"] != user_id:
                    continue

                current_config = user.get("llm_config") or {}
                current_cipher = current_config.get("api_key_cipher")
                if api_key:
                    current_cipher = cls._protect_secret(api_key.strip())
                if not current_cipher:
                    raise ValueError("API key is required.")

                now = datetime.utcnow().isoformat() + "Z"
                user["llm_config"] = {
                    "provider": provider,
                    "model": model,
                    "base_url": base_url,
                    "api_key_cipher": current_cipher,
                    "api_key_hint": cls._api_key_hint(api_key) if api_key else current_config.get("api_key_hint", ""),
                    "updated_at": now,
                }
                user["updated_at"] = now
                cls._save(data)
                return deepcopy(user)

        raise ValueError("User not found.")

    @classmethod
    def list_public_users(cls) -> list[Dict[str, Any]]:
        with cls._lock:
            data = cls._load()
            return [cls.public_user(user) for user in data["users"]]

    @classmethod
    def update_user(
        cls,
        user_id: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with cls._lock:
            data = cls._load()
            target = None
            for user in data["users"]:
                if user["user_id"] == user_id:
                    target = user
                    break

            if not target:
                raise ValueError("User not found.")

            if username is not None:
                username = username.strip()
                if len(username) < 3:
                    raise ValueError("Username must be at least 3 characters.")
                if any(
                    u["user_id"] != user_id and u["username"].lower() == username.lower()
                    for u in data["users"]
                ):
                    raise ValueError("Username already exists.")
                target["username"] = username

            if password:
                if len(password) < 8:
                    raise ValueError("Password must be at least 8 characters.")
                target["password_hash"] = generate_password_hash(password)

            if llm_config is not None:
                provider = (llm_config.get("provider") or "").strip().lower()
                if llm_config.get("clear"):
                    target["llm_config"] = None
                elif provider:
                    if provider not in LLM_PROVIDER_DEFAULTS:
                        raise ValueError("Unsupported LLM provider.")
                    defaults = LLM_PROVIDER_DEFAULTS[provider]
                    current = target.get("llm_config") or {}
                    api_key = (llm_config.get("api_key") or "").strip()
                    api_key_cipher = cls._protect_secret(api_key) if api_key else current.get("api_key_cipher")
                    target["llm_config"] = {
                        "provider": provider,
                        "model": (llm_config.get("model") or defaults["default_model"]).strip(),
                        "base_url": (llm_config.get("base_url") or defaults["base_url"]).strip().rstrip("/"),
                        "api_key_cipher": api_key_cipher,
                        "api_key_hint": cls._api_key_hint(api_key) if api_key else current.get("api_key_hint", ""),
                        "updated_at": datetime.utcnow().isoformat() + "Z",
                    }

            target["updated_at"] = datetime.utcnow().isoformat() + "Z"
            cls._save(data)
            return deepcopy(target)

    @classmethod
    def get_llm_config(cls, user_id: str) -> Optional[Dict[str, str]]:
        user = cls.get_user(user_id)
        if not user or not user.get("llm_config"):
            return None

        config = user["llm_config"]
        api_key_cipher = config.get("api_key_cipher")
        if not api_key_cipher:
            return None

        return {
            "provider": config.get("provider", "openai"),
            "model": config.get("model") or LLM_PROVIDER_DEFAULTS["openai"]["default_model"],
            "base_url": config.get("base_url") or LLM_PROVIDER_DEFAULTS["openai"]["base_url"],
            "api_key": cls._unprotect_secret(api_key_cipher),
        }

    @classmethod
    def public_user(cls, user: Dict[str, Any]) -> Dict[str, Any]:
        llm_config = user.get("llm_config") or {}
        return {
            "user_id": user.get("user_id"),
            "username": user.get("username"),
            "role": user.get("role", "user"),
            "is_admin": user.get("role") == "admin",
            "created_at": user.get("created_at"),
            "llm_configured": bool(llm_config.get("api_key_cipher")),
            "llm": {
                "provider": llm_config.get("provider"),
                "model": llm_config.get("model"),
                "base_url": llm_config.get("base_url"),
                "api_key_hint": llm_config.get("api_key_hint"),
                "updated_at": llm_config.get("updated_at"),
            } if llm_config else None,
        }

    @classmethod
    def _api_key_hint(cls, api_key: Optional[str]) -> str:
        if not api_key:
            return ""
        key = api_key.strip()
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"

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
    def _secret_stream(cls, length: int) -> bytes:
        secret = Config.SECRET_KEY.encode("utf-8")
        output = bytearray()
        counter = 0
        while len(output) < length:
            output.extend(hashlib.sha256(secret + counter.to_bytes(8, "big")).digest())
            counter += 1
        return bytes(output[:length])
