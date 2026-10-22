"""Add platform_models, users.platform_model_id, and drop max_agents from tiers

platform_models: site-provided LLM APIs managed in /admin; Premium subscribers
can use them without their own API key.

users.platform_model_id: the platform model a user has selected (NULL = use the
user's own llm_config). No FK on purpose — keeps the SQLite migration a plain
ADD COLUMN and lets admins delete a model without cascading.

Plans no longer advertise an AI-agent cap, so the legacy "max_agents" flag is
removed from every tier, and an empty Premium tier gets its new defaults.

Revision ID: 007
Revises: 006
Create Date: 2026-10-22
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PREMIUM_FLAGS = {
    "sim_runs_per_month": 10,
    "report_export": True,
    "platform_models": True,
}


def upgrade() -> None:
    op.create_table(
        "platform_models",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("label", sa.String(100), nullable=False, server_default=""),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("api_key_cipher", sa.Text(), nullable=False),
        sa.Column("api_key_hint", sa.String(50), nullable=False, server_default=""),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("platform_model_id", sa.Integer(), nullable=True),
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT tier_code, feature_flags FROM subscription_tiers")
    ).fetchall()
    for tier_code, raw in rows:
        try:
            flags = json.loads(raw) if raw else {}
        except (ValueError, TypeError):
            continue
        if not isinstance(flags, dict):
            continue
        changed = flags.pop("max_agents", None) is not None
        if tier_code == "premium" and not flags:
            flags = dict(_PREMIUM_FLAGS)
            changed = True
        if changed:
            bind.execute(
                sa.text(
                    "UPDATE subscription_tiers SET feature_flags = :f "
                    "WHERE tier_code = :c"
                ),
                {"f": json.dumps(flags, ensure_ascii=False), "c": tier_code},
            )


def downgrade() -> None:
    op.drop_column("users", "platform_model_id")
    op.drop_table("platform_models")
