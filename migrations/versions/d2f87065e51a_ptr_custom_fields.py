"""Add optional customer-defined fields to pressure test records.

Revision ID: d2f87065e51a
Revises: a83e76f92c10
Create Date: 2026-09-01 15:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d2f87065e51a"
down_revision: Union[str, None] = "a83e76f92c10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("pressure_test_records")}
    if "custom_fields" not in columns:
        op.add_column(
            "pressure_test_records",
            sa.Column("custom_fields", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("pressure_test_records")}
    if "custom_fields" in columns:
        op.drop_column("pressure_test_records", "custom_fields")