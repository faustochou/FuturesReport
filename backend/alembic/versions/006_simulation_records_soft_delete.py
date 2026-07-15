"""Add full_requirement and deleted_at to simulation_records

full_requirement: untruncated simulation_requirement text (title stays
VARCHAR(200) and truncated for backward compat; reads prefer this new
column, see api/simulation.py _to_dict).

deleted_at: nullable timestamp for user-initiated soft delete of a
recorded simulation run (DELETE /api/simulation/records/<id>).

Revision ID: 006
Revises: 005
Create Date: 2026-07-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "simulation_records",
        sa.Column("full_requirement", sa.Text(), nullable=True),
    )
    op.add_column(
        "simulation_records",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_simulation_records_deleted_at", "simulation_records", ["deleted_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_simulation_records_deleted_at", table_name="simulation_records")
    op.drop_column("simulation_records", "deleted_at")
    op.drop_column("simulation_records", "full_requirement")
