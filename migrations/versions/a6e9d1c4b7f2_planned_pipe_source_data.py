"""Store copied PipeCloud source columns for planned pipes.

Revision ID: a6e9d1c4b7f2
Revises: f4d2a8e7c9b1
Create Date: 2026-09-03 11:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a6e9d1c4b7f2"
down_revision: Union[str, None] = "f4d2a8e7c9b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "planned_test_pipes",
        sa.Column("source_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("planned_test_pipes", "source_data")