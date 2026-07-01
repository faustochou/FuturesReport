"""Add subscription_tiers and user_subscriptions tables

Revision ID: 002
Revises: 001
Create Date: 2026-07-01
"""

import json
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Seed data ----------------------------------------------------------------
_TIERS = [
    {
        "tier_code": "lite",
        "display_name": "Lite",
        "stripe_price_id": None,
        "is_available": True,
        "feature_flags": json.dumps({
            "max_agents": 100,
            "sim_runs_per_month": 10,
            "report_export": True,
        }),
        "updated_at": datetime.utcnow(),
    },
    {
        "tier_code": "premium",
        "display_name": "Premium",
        "stripe_price_id": None,
        "is_available": False,
        "feature_flags": json.dumps({}),
        "updated_at": datetime.utcnow(),
    },
    {
        "tier_code": "pro",
        "display_name": "Pro",
        "stripe_price_id": None,
        "is_available": False,
        "feature_flags": json.dumps({}),
        "updated_at": datetime.utcnow(),
    },
]
# --------------------------------------------------------------------------


def upgrade() -> None:
    op.create_table(
        "subscription_tiers",
        sa.Column("tier_code", sa.String(20), primary_key=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("stripe_price_id", sa.String(255), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("feature_flags", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "tier_code",
            sa.String(20),
            sa.ForeignKey("subscription_tiers.tier_code"),
            nullable=False,
        ),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True, unique=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_user_subscriptions_stripe_customer_id",
        "user_subscriptions",
        ["stripe_customer_id"],
    )
    op.create_index(
        "ix_user_subscriptions_stripe_subscription_id",
        "user_subscriptions",
        ["stripe_subscription_id"],
    )

    # Seed the three tiers
    tiers_table = sa.table(
        "subscription_tiers",
        sa.column("tier_code", sa.String),
        sa.column("display_name", sa.String),
        sa.column("stripe_price_id", sa.String),
        sa.column("is_available", sa.Boolean),
        sa.column("feature_flags", sa.Text),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(tiers_table, _TIERS)


def downgrade() -> None:
    op.drop_index(
        "ix_user_subscriptions_stripe_subscription_id",
        table_name="user_subscriptions",
    )
    op.drop_index(
        "ix_user_subscriptions_stripe_customer_id",
        table_name="user_subscriptions",
    )
    op.drop_table("user_subscriptions")
    op.drop_table("subscription_tiers")
