"""Add simulation_records table

Revision ID: 003
Revises: 002
Create Date: 2026-07-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_records",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("simulation_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(64), nullable=True),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("report_filenames", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("result_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_simulation_records_user_id", "simulation_records", ["user_id"])
    op.create_index(
        "ix_simulation_records_simulation_id",
        "simulation_records",
        ["simulation_id"],
        unique=True,
    )
    op.create_index(
        "ix_simulation_records_started_at", "simulation_records", ["started_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_simulation_records_started_at", table_name="simulation_records")
    op.drop_index("ix_simulation_records_simulation_id", table_name="simulation_records")
    op.drop_index("ix_simulation_records_user_id", table_name="simulation_records")
    op.drop_table("simulation_records")
