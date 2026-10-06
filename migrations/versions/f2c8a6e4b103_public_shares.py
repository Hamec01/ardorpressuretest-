"""Add token-based public share links; keep old /share/{log_no} links of existing logs.

Creates public_shares and one legacy record (legacy_log_no_access=true, no author)
for every pressure test that exists at upgrade time, so links already sent by
log number keep working (owner decision 2026-10-06, docs/ACCESS_PLAN_R4-R7.md).

Revision ID: f2c8a6e4b103
Revises: e5b1d7a3c902
Create Date: 2026-10-06 15:00:00.000000
"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f2c8a6e4b103"
down_revision: Union[str, None] = "e5b1d7a3c902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    public_shares = op.create_table(
        "public_shares",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("resource_type", sa.String(length=16), nullable=False),
        sa.Column("pressure_test_id", sa.String(length=36), nullable=False),
        sa.Column("legacy_log_no_access", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("resource_type IN ('log')", name="ck_public_shares_resource_type"),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_user_id IS NULL) OR revoked_at IS NOT NULL",
            name="ck_public_shares_revoked_by_requires_revoked_at",
        ),
        sa.ForeignKeyConstraint(["pressure_test_id"], ["pressure_tests.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_public_shares_pressure_test_id", "public_shares", ["pressure_test_id"], unique=False)

    test_ids = [row[0] for row in op.get_bind().execute(sa.text("SELECT id FROM pressure_tests")).fetchall()]
    if test_ids:
        now = datetime.now(timezone.utc)
        op.bulk_insert(public_shares, [
            {
                "id": str(uuid.uuid4()),
                "resource_type": "log",
                "pressure_test_id": test_id,
                "legacy_log_no_access": True,
                "created_by_user_id": None,
                "created_at": now,
                "revoked_at": None,
                "revoked_by_user_id": None,
                "last_accessed_at": None,
                "access_count": 0,
            }
            for test_id in test_ids
        ])


def downgrade() -> None:
    op.drop_index("ix_public_shares_pressure_test_id", table_name="public_shares")
    op.drop_table("public_shares")
