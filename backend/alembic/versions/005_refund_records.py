"""Add refund_records table for admin-initiated Stripe refunds

Revision ID: 005
Revises: 004
Create Date: 2026-07-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refund_records",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=False),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=False),
        sa.Column("stripe_refund_id", sa.String(255), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "admin_user_id",
            sa.String(64),
            sa.ForeignKey("users.user_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_refund_records_user_id", "refund_records", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_refund_records_user_id", table_name="refund_records")
    op.drop_table("refund_records")
