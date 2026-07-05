"""
Public settings API – no auth required.
Currently exposes site-wide social link URLs so the footer can read them.
"""

from flask import jsonify
from sqlalchemy import select

from . import settings_bp
from ..db.database import get_db
from ..db.models import SiteSettings

SOCIAL_KEYS = ["social_facebook", "social_x", "social_instagram", "social_threads", "social_github"]


@settings_bp.route("/social", methods=["GET"])
def get_social_links():
    """Return current social link URLs. Empty string means the icon is hidden."""
    with get_db() as db:
        rows = db.execute(
            select(SiteSettings).where(SiteSettings.key.in_(SOCIAL_KEYS))
        ).scalars().all()
    data = {r.key: r.value or "" for r in rows}
    for k in SOCIAL_KEYS:
        data.setdefault(k, "")
    return jsonify({"success": True, "data": data})
