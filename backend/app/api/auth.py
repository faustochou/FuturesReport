"""
Account and LLM provider settings API.
"""

from flask import jsonify, request

from . import auth_bp
from ..models.user import UserManager
from ..services import platform_model_service
from ..utils.auth import current_user, require_auth


@auth_bp.route("/providers", methods=["GET"])
def list_llm_providers():
    return jsonify({
        "success": True,
        "data": {
            "providers": UserManager.providers()
        }
    })


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    try:
        user = UserManager.create_user(
            username=data.get("username", ""),
            password=data.get("password", ""),
        )
        token = UserManager.issue_token(user["user_id"])
        return jsonify({
            "success": True,
            "data": {
                "token": token,
                "user": UserManager.public_user(user),
            }
        }), 201
    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    user = UserManager.authenticate(
        username=data.get("username", ""),
        password=data.get("password", ""),
    )
    if not user:
        return jsonify({
            "success": False,
            "error": "Invalid username or password.",
        }), 401

    token = UserManager.issue_token(user["user_id"])
    return jsonify({
        "success": True,
        "data": {
            "token": token,
            "user": UserManager.public_user(user),
        }
    })


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    return jsonify({
        "success": True,
        "data": {
            "user": UserManager.public_user(current_user())
        }
    })


@auth_bp.route("/llm-config", methods=["PUT"])
@require_auth
def update_llm_config():
    data = request.get_json() or {}
    user = current_user()
    try:
        updated = UserManager.set_llm_config(
            user_id=user["user_id"],
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            api_key=data.get("api_key"),
            base_url=data.get("base_url"),
        )
        return jsonify({
            "success": True,
            "data": {
                "user": UserManager.public_user(updated),
            }
        })
    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400


@auth_bp.route("/platform-models", methods=["GET"])
@require_auth
def list_platform_models():
    """Site-provided models. Only entitled users (Premium/Pro/admin) get a list;
    everyone else gets entitled=false and an empty list."""
    user = current_user()
    entitled = platform_model_service.user_can_use_platform_models(user)
    return jsonify({
        "success": True,
        "data": {
            "entitled": entitled,
            "models": platform_model_service.list_public_models() if entitled else [],
        },
    })


@auth_bp.route("/platform-model", methods=["PUT"])
@require_auth
def select_platform_model():
    """Choose a site-provided model (platform_model_id) or null to use own API."""
    data = request.get_json() or {}
    raw_id = data.get("platform_model_id")
    if raw_id in (None, ""):
        model_id = None
    else:
        try:
            model_id = int(raw_id)
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "error": "platform_model_id must be an integer or null.",
            }), 400

    try:
        updated = UserManager.set_platform_model(
            current_user()["user_id"], model_id
        )
    except PermissionError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "code": "SUBSCRIPTION_REQUIRED",
        }), 403
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    return jsonify({
        "success": True,
        "data": {"user": UserManager.public_user(updated)},
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    return jsonify({
        "success": True,
        "data": {}
    })
