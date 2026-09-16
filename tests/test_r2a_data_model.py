"""Regression guard for the R2a additive schema (Gauge registry, TestRevision gauge
selection, created_by/updated_by/responsible_user_id actor references, User.last_login_at).

Covers only the ORM/model shape - the actual Alembic migration (addffa66a1d8) is
verified separately against a throwaway PostgreSQL instance (upgrade -> inspect ->
downgrade -> schema diff against the pre-migration baseline), not here, since SQLite
does not exercise the same FK/constraint semantics.

Isolated by design, same pattern as the other regression tests in this repo: a private
in-memory SQLite session, never the process-wide engine. DATABASE_URL / STORAGE_DIR must
still be exported to isolated temporary values by the caller, because
services.api.config.Settings() is constructed at first import time.
"""
import os

_db_url = os.environ.get("DATABASE_URL", "")
_storage_dir = os.environ.get("STORAGE_DIR", "")

if not _db_url or "5432" in _db_url or "postgres" in _db_url.lower() or "ardor_pressure_test" in _db_url:
    raise RuntimeError(
        "DATABASE_URL is missing or looks like the staging Postgres target. "
        "Export an isolated temporary DATABASE_URL before running this test."
    )
if not _storage_dir or os.path.normpath(_storage_dir) == "/data/storage":
    raise RuntimeError(
        "STORAGE_DIR is missing or points at the staging storage volume (/data/storage). "
        "Export an isolated temporary STORAGE_DIR before running this test."
    )

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.database import Base
from services.api.models import (
    Gauge,
    PlannedTestList,
    PressureTest,
    PressureTestRecord,
    TestRevision as RevisionModel,
    User,
)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# --- User: default role, last_login_at ---------------------------------------------

def test_new_user_defaults_to_viewer_role(db_session):
    u = User(username="new_person", hashed_password="x")
    db_session.add(u)
    db_session.commit()
    assert u.role == "viewer"


def test_user_last_login_at_is_nullable_and_defaults_to_none(db_session):
    u = User(username="someone", hashed_password="x", role="admin")
    db_session.add(u)
    db_session.commit()
    assert u.last_login_at is None


# --- Gauge: strictly minimal, serial_number required + unique ----------------------

def test_gauge_table_has_exactly_the_five_expected_columns():
    columns = {c.name for c in Gauge.__table__.columns}
    assert columns == {"id", "serial_number", "is_active", "created_at", "updated_at"}


def test_gauge_serial_number_is_required(db_session):
    g = Gauge(serial_number=None)
    db_session.add(g)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_gauge_serial_number_is_unique(db_session):
    db_session.add(Gauge(serial_number="SN-0001"))
    db_session.commit()

    db_session.add(Gauge(serial_number="SN-0001"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_gauge_is_active_defaults_true(db_session):
    g = Gauge(serial_number="SN-0002")
    db_session.add(g)
    db_session.commit()
    assert g.is_active is True


# --- TestRevision: gauge selection + actor references, all nullable ----------------

def test_revision_can_be_created_without_any_new_r2a_fields(db_session):
    test = PressureTest(log_no="LOG-1")
    db_session.add(test)
    db_session.commit()

    rev = RevisionModel(pressure_test_id=test.id, revision_id="r1")
    db_session.add(rev)
    db_session.commit()

    assert rev.gauge_id is None
    assert rev.gauge_serial_snapshot is None
    assert rev.created_by_user_id is None
    assert rev.updated_by_user_id is None


def test_revision_can_reference_a_gauge_and_carry_a_snapshot(db_session):
    test = PressureTest(log_no="LOG-2")
    gauge = Gauge(serial_number="SN-0003")
    db_session.add_all([test, gauge])
    db_session.commit()

    rev = RevisionModel(
        pressure_test_id=test.id, revision_id="r1",
        gauge_id=gauge.id, gauge_serial_snapshot=gauge.serial_number,
    )
    db_session.add(rev)
    db_session.commit()

    assert rev.gauge_id == gauge.id
    assert rev.gauge_serial_snapshot == "SN-0003"


def test_revision_gauge_selection_can_change_freely_in_draft(db_session):
    """Draft-stage behavior: gauge_id and gauge_serial_snapshot are updated together
    whenever the selection changes - there is no rule blocking a change right after the
    first selection. Freezing only happens at the Complete transition (an API-layer rule
    for a later stage, not something R2a's schema itself enforces)."""
    test = PressureTest(log_no="LOG-3")
    gauge_a = Gauge(serial_number="SN-A")
    gauge_b = Gauge(serial_number="SN-B")
    db_session.add_all([test, gauge_a, gauge_b])
    db_session.commit()

    rev = RevisionModel(
        pressure_test_id=test.id, revision_id="r1", status="draft",
        gauge_id=gauge_a.id, gauge_serial_snapshot=gauge_a.serial_number,
    )
    db_session.add(rev)
    db_session.commit()

    rev.gauge_id = gauge_b.id
    rev.gauge_serial_snapshot = gauge_b.serial_number
    db_session.commit()

    assert rev.gauge_id == gauge_b.id
    assert rev.gauge_serial_snapshot == "SN-B"


# --- new actor-reference columns exist and are nullable on every target table ------

@pytest.mark.parametrize("model,fields", [
    (PressureTest, ("created_by_user_id", "updated_by_user_id", "responsible_user_id")),
    (RevisionModel, ("created_by_user_id", "updated_by_user_id")),
    (PressureTestRecord, ("created_by_user_id", "updated_by_user_id", "responsible_user_id")),
    (PlannedTestList, ("updated_by_user_id", "responsible_user_id")),
])
def test_new_actor_columns_are_nullable(model, fields):
    columns = {c.name: c for c in model.__table__.columns}
    for field in fields:
        assert field in columns, f"{model.__name__}.{field} is missing"
        assert columns[field].nullable is True, f"{model.__name__}.{field} must be nullable in R2a"


def test_planned_test_list_created_by_user_id_is_untouched(db_session):
    """R2a must never add a FK to the pre-existing legacy created_by_user_id column -
    only the new updated_by_user_id/responsible_user_id columns are real FKs."""
    columns = {c.name: c for c in PlannedTestList.__table__.columns}
    assert columns["created_by_user_id"].nullable is True
    assert len(columns["created_by_user_id"].foreign_keys) == 0


# --- FK shape: real FK, no cascade delete, on every new column ---------------------

@pytest.mark.parametrize("table_name,column,ref_table", [
    ("pressure_tests", "created_by_user_id", "users"),
    ("pressure_tests", "updated_by_user_id", "users"),
    ("pressure_tests", "responsible_user_id", "users"),
    ("test_revisions", "gauge_id", "gauges"),
    ("test_revisions", "created_by_user_id", "users"),
    ("test_revisions", "updated_by_user_id", "users"),
    ("pressure_test_records", "created_by_user_id", "users"),
    ("pressure_test_records", "updated_by_user_id", "users"),
    ("pressure_test_records", "responsible_user_id", "users"),
    ("planned_test_lists", "updated_by_user_id", "users"),
    ("planned_test_lists", "responsible_user_id", "users"),
])
def test_new_column_is_a_real_fk_without_cascade_delete(table_name, column, ref_table):
    table = Base.metadata.tables[table_name]
    col = table.columns[column]
    assert len(col.foreign_keys) == 1, f"{table_name}.{column} must have exactly one FK"
    fk = next(iter(col.foreign_keys))
    assert fk.column.table.name == ref_table
    assert fk.ondelete not in ("CASCADE",), f"{table_name}.{column} must not cascade delete"


def test_legacy_user_id_columns_remain_without_fk():
    """Regression guard: the four pre-existing semantic *_user_id columns (audit actor,
    historical creator, historical confirmer, historical pipecloud editor) must remain
    exactly as they were - no FK added, nothing rewritten by R2a."""
    checks = [
        ("audit_events", "user_id"),
        ("planned_test_lists", "created_by_user_id"),
        ("pressure_test_records", "confirmed_by_user_id"),
        ("pressure_tests", "pipecloud_updated_by_user_id"),
    ]
    for table_name, column in checks:
        table = Base.metadata.tables[table_name]
        col = table.columns[column]
        assert len(col.foreign_keys) == 0, f"{table_name}.{column} must not gain a FK"
        assert col.nullable is True


# --- end-to-end: PressureTest + TestRevision + Gauge + responsible/actor users -----

def test_full_r2a_shape_end_to_end(db_session):
    owner = User(username="andrei.sakki", hashed_password="x", role="admin")
    creator = User(username="creator", hashed_password="x", role="foreman")
    db_session.add_all([owner, creator])
    db_session.commit()

    gauge = Gauge(serial_number="SN-9999")
    db_session.add(gauge)
    db_session.commit()

    test = PressureTest(
        log_no="LOG-4",
        created_by_user_id=creator.id,
        updated_by_user_id=creator.id,
        responsible_user_id=owner.id,
    )
    db_session.add(test)
    db_session.commit()

    rev = RevisionModel(
        pressure_test_id=test.id, revision_id="r1", status="draft",
        gauge_id=gauge.id, gauge_serial_snapshot=gauge.serial_number,
        created_by_user_id=creator.id, updated_by_user_id=creator.id,
    )
    db_session.add(rev)
    db_session.commit()

    refreshed = db_session.query(PressureTest).filter(PressureTest.id == test.id).first()
    assert refreshed.responsible_user_id == owner.id
    assert refreshed.created_by_user_id == creator.id
    assert refreshed.revisions[0].gauge_serial_snapshot == "SN-9999"
