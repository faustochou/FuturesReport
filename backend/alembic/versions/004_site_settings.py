"""Add site_settings table for admin-configurable key-value settings

Revision ID: 004
Revises: 003
Create Date: 2026-07-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SOCIAL_KEYS = [
    "social_facebook",
    "social_x",
    "social_instagram",
    "social_threads",
    "social_github",
]


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    from datetime import datetime
    op.bulk_insert(
        sa.table(
            "site_settings",
            sa.column("key", sa.String),
            sa.column("value", sa.Text),
            sa.column("updated_at", sa.DateTime),
        ),
        [{"key": k, "value": "", "updated_at": datetime.utcnow()} for k in SOCIAL_KEYS],
    )


def downgrade() -> None:
    op.drop_table("site_settings")
