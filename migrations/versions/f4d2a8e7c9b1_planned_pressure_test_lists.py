"""Add planned pressure test lists.

Revision ID: f4d2a8e7c9b1
Revises: e13c694f8a0b
Create Date: 2026-09-03 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f4d2a8e7c9b1"
down_revision: Union[str, None] = "e13c694f8a0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "planned_test_lists",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_planned_test_lists_is_archived", "planned_test_lists", ["is_archived"], unique=False)
    op.create_table(
        "planned_test_pipes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("planned_test_list_id", sa.String(length=36), nullable=False),
        sa.Column("pipe_number", sa.String(length=128), nullable=False),
        sa.Column("bundle_number", sa.String(length=128), nullable=False),
        sa.Column("pipe_sort_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["planned_test_list_id"], ["planned_test_lists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("planned_test_list_id", "pipe_number", name="uq_planned_test_pipes_list_pipe"),
    )
    op.create_index("ix_planned_test_pipes_planned_test_list_id", "planned_test_pipes", ["planned_test_list_id"], unique=False)
    op.create_index("ix_planned_test_pipes_pipe_number", "planned_test_pipes", ["pipe_number"], unique=False)
    op.create_index("ix_planned_test_pipes_bundle_number", "planned_test_pipes", ["bundle_number"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_planned_test_pipes_bundle_number", table_name="planned_test_pipes")
    op.drop_index("ix_planned_test_pipes_pipe_number", table_name="planned_test_pipes")
    op.drop_index("ix_planned_test_pipes_planned_test_list_id", table_name="planned_test_pipes")
    op.drop_table("planned_test_pipes")
    op.drop_index("ix_planned_test_lists_is_archived", table_name="planned_test_lists")
    op.drop_table("planned_test_lists")