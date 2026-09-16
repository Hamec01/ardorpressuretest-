"""R2a: additive nullable schema - gauges registry, TestRevision gauge selection,
created_by/updated_by/responsible_user_id actor references, User.last_login_at.

Revision ID: addffa66a1d8
Revises: a6e9d1c4b7f2
Create Date: 2026-09-17 09:00:00.000000

Purely additive: every new column is nullable, every new table starts empty, and no
existing column, constraint, or data is modified. No backfill runs here (that is R2b/
R2c). The pre-existing pipecloud_updated_by_user_id / planned_test_lists.created_by_
user_id / pressure_test_records.confirmed_by_user_id / audit_events.user_id columns are
untouched - they keep their original (no foreign key) shape.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "addffa66a1d8"
down_revision: Union[str, None] = "a6e9d1c4b7f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "gauges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("serial_number", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_gauges_serial_number"), "gauges", ["serial_number"], unique=True)

    op.add_column("test_revisions", sa.Column("gauge_id", sa.String(length=36), nullable=True))
    op.add_column("test_revisions", sa.Column("gauge_serial_snapshot", sa.String(length=128), nullable=True))
    op.add_column("test_revisions", sa.Column("created_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("test_revisions", sa.Column("updated_by_user_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_test_revisions_gauge_id"), "test_revisions", ["gauge_id"], unique=False)
    op.create_index(op.f("ix_test_revisions_created_by_user_id"), "test_revisions", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_test_revisions_updated_by_user_id"), "test_revisions", ["updated_by_user_id"], unique=False)
    op.create_foreign_key("test_revisions_gauge_id_fkey", "test_revisions", "gauges", ["gauge_id"], ["id"])
    op.create_foreign_key("test_revisions_created_by_user_id_fkey", "test_revisions", "users", ["created_by_user_id"], ["id"])
    op.create_foreign_key("test_revisions_updated_by_user_id_fkey", "test_revisions", "users", ["updated_by_user_id"], ["id"])

    op.add_column("pressure_tests", sa.Column("created_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("pressure_tests", sa.Column("updated_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("pressure_tests", sa.Column("responsible_user_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_pressure_tests_created_by_user_id"), "pressure_tests", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_pressure_tests_updated_by_user_id"), "pressure_tests", ["updated_by_user_id"], unique=False)
    op.create_index(op.f("ix_pressure_tests_responsible_user_id"), "pressure_tests", ["responsible_user_id"], unique=False)
    op.create_foreign_key("pressure_tests_created_by_user_id_fkey", "pressure_tests", "users", ["created_by_user_id"], ["id"])
    op.create_foreign_key("pressure_tests_updated_by_user_id_fkey", "pressure_tests", "users", ["updated_by_user_id"], ["id"])
    op.create_foreign_key("pressure_tests_responsible_user_id_fkey", "pressure_tests", "users", ["responsible_user_id"], ["id"])

    op.add_column("pressure_test_records", sa.Column("created_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("pressure_test_records", sa.Column("updated_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("pressure_test_records", sa.Column("responsible_user_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_pressure_test_records_created_by_user_id"), "pressure_test_records", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_pressure_test_records_updated_by_user_id"), "pressure_test_records", ["updated_by_user_id"], unique=False)
    op.create_index(op.f("ix_pressure_test_records_responsible_user_id"), "pressure_test_records", ["responsible_user_id"], unique=False)
    op.create_foreign_key("pressure_test_records_created_by_user_id_fkey", "pressure_test_records", "users", ["created_by_user_id"], ["id"])
    op.create_foreign_key("pressure_test_records_updated_by_user_id_fkey", "pressure_test_records", "users", ["updated_by_user_id"], ["id"])
    op.create_foreign_key("pressure_test_records_responsible_user_id_fkey", "pressure_test_records", "users", ["responsible_user_id"], ["id"])

    op.add_column("planned_test_lists", sa.Column("updated_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("planned_test_lists", sa.Column("responsible_user_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_planned_test_lists_updated_by_user_id"), "planned_test_lists", ["updated_by_user_id"], unique=False)
    op.create_index(op.f("ix_planned_test_lists_responsible_user_id"), "planned_test_lists", ["responsible_user_id"], unique=False)
    op.create_foreign_key("planned_test_lists_updated_by_user_id_fkey", "planned_test_lists", "users", ["updated_by_user_id"], ["id"])
    op.create_foreign_key("planned_test_lists_responsible_user_id_fkey", "planned_test_lists", "users", ["responsible_user_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("planned_test_lists_responsible_user_id_fkey", "planned_test_lists", type_="foreignkey")
    op.drop_constraint("planned_test_lists_updated_by_user_id_fkey", "planned_test_lists", type_="foreignkey")
    op.drop_index(op.f("ix_planned_test_lists_responsible_user_id"), table_name="planned_test_lists")
    op.drop_index(op.f("ix_planned_test_lists_updated_by_user_id"), table_name="planned_test_lists")
    op.drop_column("planned_test_lists", "responsible_user_id")
    op.drop_column("planned_test_lists", "updated_by_user_id")

    op.drop_constraint("pressure_test_records_responsible_user_id_fkey", "pressure_test_records", type_="foreignkey")
    op.drop_constraint("pressure_test_records_updated_by_user_id_fkey", "pressure_test_records", type_="foreignkey")
    op.drop_constraint("pressure_test_records_created_by_user_id_fkey", "pressure_test_records", type_="foreignkey")
    op.drop_index(op.f("ix_pressure_test_records_responsible_user_id"), table_name="pressure_test_records")
    op.drop_index(op.f("ix_pressure_test_records_updated_by_user_id"), table_name="pressure_test_records")
    op.drop_index(op.f("ix_pressure_test_records_created_by_user_id"), table_name="pressure_test_records")
    op.drop_column("pressure_test_records", "responsible_user_id")
    op.drop_column("pressure_test_records", "updated_by_user_id")
    op.drop_column("pressure_test_records", "created_by_user_id")

    op.drop_constraint("pressure_tests_responsible_user_id_fkey", "pressure_tests", type_="foreignkey")
    op.drop_constraint("pressure_tests_updated_by_user_id_fkey", "pressure_tests", type_="foreignkey")
    op.drop_constraint("pressure_tests_created_by_user_id_fkey", "pressure_tests", type_="foreignkey")
    op.drop_index(op.f("ix_pressure_tests_responsible_user_id"), table_name="pressure_tests")
    op.drop_index(op.f("ix_pressure_tests_updated_by_user_id"), table_name="pressure_tests")
    op.drop_index(op.f("ix_pressure_tests_created_by_user_id"), table_name="pressure_tests")
    op.drop_column("pressure_tests", "responsible_user_id")
    op.drop_column("pressure_tests", "updated_by_user_id")
    op.drop_column("pressure_tests", "created_by_user_id")

    op.drop_constraint("test_revisions_updated_by_user_id_fkey", "test_revisions", type_="foreignkey")
    op.drop_constraint("test_revisions_created_by_user_id_fkey", "test_revisions", type_="foreignkey")
    op.drop_constraint("test_revisions_gauge_id_fkey", "test_revisions", type_="foreignkey")
    op.drop_index(op.f("ix_test_revisions_updated_by_user_id"), table_name="test_revisions")
    op.drop_index(op.f("ix_test_revisions_created_by_user_id"), table_name="test_revisions")
    op.drop_index(op.f("ix_test_revisions_gauge_id"), table_name="test_revisions")
    op.drop_column("test_revisions", "updated_by_user_id")
    op.drop_column("test_revisions", "created_by_user_id")
    op.drop_column("test_revisions", "gauge_serial_snapshot")
    op.drop_column("test_revisions", "gauge_id")

    op.drop_index(op.f("ix_gauges_serial_number"), table_name="gauges")
    op.drop_table("gauges")

    op.drop_column("users", "last_login_at")
