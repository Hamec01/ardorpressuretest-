"""Add one-time password set/reset links for admin account management.

Revision ID: e5b1d7a3c902
Revises: c7f2e8a4b901
Create Date: 2026-10-06 13:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5b1d7a3c902"
down_revision: Union[str, None] = "c7f2e8a4b901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("purpose IN ('invite', 'reset')", name="ck_password_links_purpose"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_password_links_token_hash_length"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_password_links_user_id", "password_links", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_password_links_user_id", table_name="password_links")
    op.drop_table("password_links")
