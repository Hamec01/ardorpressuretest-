"""Allow archived tests to reuse log numbers without blocking active tests.

Revision ID: e13c694f8a0b
Revises: d2f87065e51a
Create Date: 2026-09-02 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e13c694f8a0b"
down_revision: Union[str, None] = "d2f87065e51a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("pressure_tests")}
    if "ix_pressure_tests_log_no" in indexes:
        op.drop_index("ix_pressure_tests_log_no", table_name="pressure_tests")
    if "uq_pressure_tests_active_log_no" not in indexes:
        op.create_index(
            "uq_pressure_tests_active_log_no",
            "pressure_tests",
            ["log_no"],
            unique=True,
            postgresql_where=sa.text("is_archived = false"),
        )


def downgrade() -> None:
    op.drop_index("uq_pressure_tests_active_log_no", table_name="pressure_tests")
    op.create_index("ix_pressure_tests_log_no", "pressure_tests", ["log_no"], unique=True)