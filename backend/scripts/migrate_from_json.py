"""
One-shot migration: import users from the legacy users.json into the database.

Usage (run from backend/ directory):
    uv run python scripts/migrate_from_json.py

The script is idempotent: it skips users whose username already exists in the DB.
"""

import json
import os
import sys
from datetime import datetime

# Make the app package importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

_root = os.path.join(os.path.dirname(__file__), "../../")
load_dotenv(os.path.join(_root, ".env"), override=True)

from app.db.database import create_tables, get_db  # noqa: E402
from app.db.models import LlmConfig, User  # noqa: E402
from app.config import Config  # noqa: E402
from sqlalchemy import func, select  # noqa: E402


def _find_json_path() -> str:
    candidates = [
        Config.USER_DATA_FILE,
        Config.LEGACY_USER_DATA_FILE,
        os.path.join(os.path.dirname(__file__), "../../uploads/users.json"),
        "/data/users.json",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return ""


def main() -> None:
    json_path = _find_json_path()
    if not json_path:
        print("✗ users.json not found – nothing to migrate.")
        sys.exit(0)

    print(f"→ Reading from: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    users = data.get("users", [])
    if not users:
        print("✓ users.json is empty – nothing to migrate.")
        return

    create_tables()
    imported = 0
    skipped = 0

    with get_db() as db:
        for idx, u in enumerate(users):
            uname = (u.get("username") or "").strip()
            if not uname:
                continue

            exists = db.execute(
                select(func.count()).select_from(User).where(
                    func.lower(User.username) == uname.lower()
                )
            ).scalar_one()
            if exists:
                print(f"  skip  {uname!r} (already in DB)")
                skipped += 1
                continue

            def _dt(s):
                if not s:
                    return datetime.utcnow()
                try:
                    return datetime.fromisoformat(s.rstrip("Z"))
                except ValueError:
                    return datetime.utcnow()

            role = u.get("role", "admin" if idx == 0 else "user")
            user = User(
                user_id=u.get("user_id") or f"user_migrated_{idx:04d}",
                username=uname,
                password_hash=u.get("password_hash", ""),
                role=role,
                is_active=True,
                created_at=_dt(u.get("created_at")),
                updated_at=_dt(u.get("updated_at")),
            )
            db.add(user)

            llm = u.get("llm_config")
            if llm and llm.get("api_key_cipher"):
                cfg = LlmConfig(
                    user_id=user.user_id,
                    provider=llm.get("provider", "openai"),
                    model=llm.get("model", ""),
                    base_url=llm.get("base_url", ""),
                    api_key_cipher=llm["api_key_cipher"],
                    api_key_hint=llm.get("api_key_hint", ""),
                    updated_at=_dt(llm.get("updated_at")),
                )
                db.add(cfg)

            print(f"  import {uname!r} (role={role})")
            imported += 1

    print(f"\n✓ Done – imported {imported}, skipped {skipped}.")


if __name__ == "__main__":
    main()
