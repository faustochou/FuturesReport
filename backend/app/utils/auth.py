"""
Request authentication helpers.
"""

from functools import wraps
from typing import Any, Callable, Dict, Optional

from flask import g, jsonify, request

from ..models.user import UserManager


def get_bearer_token() -> str:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return ""


def current_user() -> Optional[Dict[str, Any]]:
    if hasattr(g, "current_user"):
        return g.current_user

    token = get_bearer_token()
    user = UserManager.verify_token(token) if token else None
    g.current_user = user
    return user


def require_auth(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        user = current_user()
        if not user:
            return jsonify({
                "success": False,
                "error": "Please log in before using this feature.",
                "code": "AUTH_REQUIRED",
            }), 401
        return fn(*args, **kwargs)

    return wrapper


def current_admin() -> Optional[Dict[str, Any]]:
    if hasattr(g, "current_admin"):
        return g.current_admin

    token = get_bearer_token()
    admin = UserManager.verify_admin_token(token) if token else None
    if not admin:
        user = UserManager.verify_token(token) if token else None
        if user and user.get("role") == "admin":
            admin = {
                "role": "admin",
                "user_id": user.get("user_id"),
                "username": user.get("username", ""),
            }
    g.current_admin = admin
    return admin


def require_admin(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        admin = current_admin()
        if not admin:
            return jsonify({
                "success": False,
                "error": "Admin authentication required.",
                "code": "ADMIN_AUTH_REQUIRED",
            }), 401
        return fn(*args, **kwargs)

    return wrapper


def get_current_llm_config() -> Optional[Dict[str, str]]:
    user = current_user()
    if not user:
        return None
    return UserManager.get_llm_config(user["user_id"])


def require_llm_config(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        user = current_user()
        if not user:
            return jsonify({
                "success": False,
                "error": "Please log in before using this feature.",
                "code": "AUTH_REQUIRED",
            }), 401

        if not UserManager.get_llm_config(user["user_id"]):
            return jsonify({
                "success": False,
                "error": "Please add your LLM provider and API key first.",
                "code": "LLM_CONFIG_REQUIRED",
            }), 400

        return fn(*args, **kwargs)

    return wrapper
