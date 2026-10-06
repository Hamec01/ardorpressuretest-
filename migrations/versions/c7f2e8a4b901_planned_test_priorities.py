"""Add optional priorities to planned pressure test lists.

Revision ID: c7f2e8a4b901
Revises: d3fc3cb2ef8b
Create Date: 2026-10-06 09:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c7f2e8a4b901"
down_revision: Union[str, None] = "d3fc3cb2ef8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "planned_test_lists",
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_check_constraint(
        "ck_planned_test_lists_priority",
        "planned_test_lists",
        "priority >= 0 AND priority <= 3",
    )
    op.create_index(
        "ix_planned_test_lists_priority",
        "planned_test_lists",
        ["priority"],
        unique=False,
    )
    op.alter_column("planned_test_lists", "priority", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_planned_test_lists_priority", table_name="planned_test_lists")
    op.drop_constraint(
        "ck_planned_test_lists_priority",
        "planned_test_lists",
        type_="check",
    )
    op.drop_column("planned_test_lists", "priority")
