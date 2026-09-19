"""R3b-1: additive session schema - sessions table + users.must_change_password.

Revision ID: d3fc3cb2ef8b
Revises: 2327325e8143
Create Date: 2026-09-19 00:00:00.000000

Schema only, per the R3 design correspondence (docs/adr/ADR-005-auth-session-model.md
§8/§9 and its R3 addenda) - no auth behavior, routes, cookie/JWT/CSRF logic, password
hashing, rate limiting, frontend, or desktop code changes anywhere in this stage. No
existing table's data is read or modified beyond the new column's default backfill.

sessions is a brand-new, empty table - nothing populates it yet. users.must_change_password
is NOT NULL DEFAULT false: Postgres backfills every existing row with false as part of
the single ADD COLUMN statement (fast, native default-fill, no separate UPDATE pass),
so every user that existed before this migration reads must_change_password=false
afterward, and no other column on users is touched.

token_hash / previous_token_hash / csrf_token_hash only ever store a SHA-256 hex digest
(64 hex chars) of a >=256-bit random secret - never the secret itself - matching the
hash-only discipline ADR-005 §10 already established for share tokens. previous_token_hash
exists only for the desktop refresh-rotation reuse-detection design; csrf_token_hash only
for the browser cookie-CSRF design - the CHECK constraints below enforce which channel
each one applies to.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d3fc3cb2ef8b"
down_revision: Union[str, None] = "2327325e8143"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # server_default only exists to backfill pre-existing rows atomically; the ORM
    # model expresses the same default in Python (default=False), not at the DB level,
    # matching how every other NOT NULL boolean in this schema (pipecloud_added,
    # is_archived, is_active, ...) is already declared - so the column-level default is
    # dropped immediately after the backfill to keep ORM and DB in exact agreement.
    op.alter_column("users", "must_change_password", server_default=None)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_token_hash", sa.String(length=64), nullable=True),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=32), nullable=True),
        sa.Column("device_label", sa.String(length=128), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("channel IN ('browser', 'desktop')", name="ck_sessions_channel"),
        sa.CheckConstraint(
            "(channel = 'browser' AND csrf_token_hash IS NOT NULL) OR "
            "(channel = 'desktop' AND csrf_token_hash IS NULL)",
            name="ck_sessions_csrf_token_hash_by_channel",
        ),
        sa.CheckConstraint(
            "previous_token_hash IS NULL OR channel = 'desktop'",
            name="ck_sessions_previous_token_hash_desktop_only",
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_reason IS NOT NULL)",
            name="ck_sessions_revoked_at_reason_together",
        ),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_sessions_token_hash_length"),
        sa.CheckConstraint(
            "previous_token_hash IS NULL OR length(previous_token_hash) = 64",
            name="ck_sessions_previous_token_hash_length",
        ),
        sa.CheckConstraint(
            "csrf_token_hash IS NULL OR length(csrf_token_hash) = 64",
            name="ck_sessions_csrf_token_hash_length",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_sessions_expires_after_created"),
    )
    op.create_foreign_key("sessions_user_id_fkey", "sessions", "users", ["user_id"], ["id"])
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_sessions_token_hash"), "sessions", ["token_hash"], unique=True)
    op.create_index(op.f("ix_sessions_expires_at"), "sessions", ["expires_at"], unique=False)
    op.create_index(
        "ix_sessions_previous_token_hash",
        "sessions",
        ["previous_token_hash"],
        unique=False,
        postgresql_where=sa.text("previous_token_hash IS NOT NULL"),
    )
    op.create_index(
        "ix_sessions_user_id_active",
        "sessions",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_user_id_active", table_name="sessions")
    op.drop_index("ix_sessions_previous_token_hash", table_name="sessions")
    op.drop_index(op.f("ix_sessions_expires_at"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_token_hash"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_constraint("sessions_user_id_fkey", "sessions", type_="foreignkey")
    op.drop_table("sessions")

    op.drop_column("users", "must_change_password")
