"""Regression guard for scripts/plan_r2_legacy_backfill.py.

Two tiers, matching the two things that need proving:
  1. Pure logic (verify_target, the per-table/per-column count functions, the planned-
     audit-event arithmetic, the finalized/unknown-status blockers) - tested here
     against an isolated in-memory SQLite session or, where no DB is needed at all,
     directly against synthetic dataclass instances. Same pattern as every other
     regression test in this repo.
  2. compute_wika_nr_stats(), the current_database()/Alembic-head checks, and the full
     run_plan()/run_dry_plan() success path use PostgreSQL-only jsonb operators
     (`::jsonb ?`) and the real `alembic_version`/`current_database()` shape, and are
     deliberately NOT exercised here - they are covered separately against a throwaway
     PostgreSQL instance upgraded to addffa66a1d8 with synthetic data (a manual CLI
     verification, not a pytest module, since it needs a real Postgres server this test
     suite does not have access to).

This file also statically proves the script has no write path at all - not a runtime
behavior test, but a direct source-text check that no destructive/mutating SQL keyword,
ORM mutation call, or --apply flag appears anywhere in the script.
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

import re
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.database import Base
from services.api.models import (
    AuditEvent,
    Gauge,
    PressureTest,
    TestRevision as RevisionModel,
    User,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.plan_r2_legacy_backfill import (  # noqa: E402
    ANDREI_USERNAME,
    EXPECTED_ALEMBIC_HEAD,
    EXPECTED_ARDOR_ENV,
    FINALIZED_STATUSES,
    PROTECTED_COLUMNS,
    RESPONSIBILITY_TABLES,
    PlanResult,
    ResponsibilityStats,
    StatusWikaNrBreakdown,
    TargetCheckResult,
    WikaNrStats,
    compute_audit_events_control_count,
    compute_finalized_without_gauge_blocker,
    compute_planned_audit_event_counts,
    compute_protected_column_stats,
    compute_r2a_field_stats,
    compute_responsibility_stats,
    compute_unknown_status_blocker,
    run_plan,
    verify_target,
)
import scripts.plan_r2_legacy_backfill as plan_module

STAGING = EXPECTED_ARDOR_ENV  # "staging" - the only environment verify_target() accepts


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


def _make_user(username, role, is_active=True):
    return User(username=username, hashed_password="x", role=role, is_active=is_active)


@pytest.fixture()
def seeded_andrei(db_session):
    andrei = _make_user(ANDREI_USERNAME, "admin")
    db_session.add(andrei)
    db_session.commit()
    return andrei


# --- verify_target(): ARDOR_ENV + dialect gate + andrei checks (SQLite exercises
#     everything except current_database()/Alembic-head, both guarded behind the
#     dialect check and covered separately against real Postgres) -------------------

def test_verify_target_fails_when_ardor_env_is_not_staging(db_session, seeded_andrei):
    for wrong_env in ("local", "dev", "production", "", "Staging"):
        check = verify_target(db_session, wrong_env)
        assert check.ardor_env_is_staging is False
        assert check.ok is False


def test_verify_target_ardor_env_flag_is_true_only_for_exact_staging(db_session, seeded_andrei):
    check = verify_target(db_session, STAGING)
    assert check.ardor_env_is_staging is True
    # still not ok overall - dialect is sqlite in this isolated test
    assert check.ok is False


def test_verify_target_fails_on_sqlite_dialect(db_session, seeded_andrei):
    check = verify_target(db_session, STAGING)
    assert check.dialect_is_postgresql is False
    assert check.ok is False
    assert any("PostgreSQL" in p for p in check.problems)


def test_verify_target_current_database_and_alembic_head_checks_are_skipped_on_non_postgres(db_session, seeded_andrei):
    """On a non-PostgreSQL dialect, current_database()/alembic_version simply do not
    exist in the same form - the checks must not attempt them and must report False
    rather than raising."""
    check = verify_target(db_session, STAGING)
    assert check.current_database_is_expected is False
    assert check.alembic_head_is_expected is False


def test_verify_target_fails_when_andrei_missing(db_session):
    check = verify_target(db_session, STAGING)
    assert check.andrei_count == 0
    assert check.ok is False
    assert any("missing" in p for p in check.problems)


def test_verify_target_duplicated_check_is_unreachable_due_to_unique_username(db_session):
    """users.username carries a UNIQUE index (confirmed in the R0 schema inventory), so
    two rows with username='andrei.sakki' cannot coexist - the "duplicated" branch in
    verify_target() is deliberate defense-in-depth, not a scenario constructible against
    the real schema. This test documents that guarantee directly rather than attempting
    an insert that would only prove SQLite's constraint enforcement, not this script's
    logic."""
    db_session.add(_make_user(ANDREI_USERNAME, "admin"))
    db_session.commit()
    db_session.add(_make_user(ANDREI_USERNAME, "admin"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_verify_target_fails_when_andrei_inactive(db_session):
    db_session.add(_make_user(ANDREI_USERNAME, "admin", is_active=False))
    db_session.commit()

    check = verify_target(db_session, STAGING)
    assert check.andrei_is_active_admin is False
    assert check.ok is False


def test_verify_target_fails_when_andrei_not_admin_role(db_session):
    db_session.add(_make_user(ANDREI_USERNAME, "foreman"))
    db_session.commit()

    check = verify_target(db_session, STAGING)
    assert check.andrei_is_active_admin is False
    assert check.ok is False


# --- run_plan(): target guards must fire before any R2a-table query ----------------

def test_target_guards_run_before_any_r2a_table_query(db_session, monkeypatch):
    """With an invalid target (wrong ARDOR_ENV here, on top of the inherent SQLite
    dialect failure), run_plan() must return immediately from verify_target() without
    ever calling any of the section-computation functions below it. Each one is
    monkeypatched to raise if called, so this test fails loudly if the ordering is ever
    broken - not just silently passing because the assertions happened to line up."""
    def _boom(*args, **kwargs):
        raise AssertionError("R2a-table query function was called despite an invalid target")

    monkeypatch.setattr(plan_module, "compute_responsibility_stats", _boom)
    monkeypatch.setattr(plan_module, "compute_protected_column_stats", _boom)
    monkeypatch.setattr(plan_module, "compute_audit_events_control_count", _boom)
    monkeypatch.setattr(plan_module, "compute_wika_nr_stats", _boom)
    monkeypatch.setattr(plan_module, "compute_r2a_field_stats", _boom)

    result = run_plan(db_session, "production")  # wrong ARDOR_ENV, also wrong dialect on SQLite

    assert result.target.ok is False
    assert result.ok is False
    assert result.responsibility_stats is None
    assert result.protected_column_stats is None
    assert result.audit_events_control_count is None
    assert result.wika_nr_stats is None
    assert result.r2a_field_stats is None
    assert result.planned_audit_events is None
    assert result.finalized_blocker is None
    assert result.unknown_status_blocker is None


# --- compute_responsibility_stats(): per-table counts -------------------------------

def test_responsibility_stats_all_null_by_default(db_session, seeded_andrei):
    db_session.add(PressureTest(log_no="L1"))
    db_session.add(PressureTest(log_no="L2"))
    db_session.commit()

    stats = compute_responsibility_stats(db_session, "pressure_tests", seeded_andrei.id)
    assert stats.total_rows == 2
    assert stats.responsible_null == 2
    assert stats.responsible_already_andrei == 0
    assert stats.responsible_assigned_to_other == 0
    assert stats.planned_assignments == 2
    assert stats.planned_audit_events == 2


def test_responsibility_stats_distinguishes_andrei_from_others(db_session, seeded_andrei):
    other = _make_user("someone_else", "foreman")
    db_session.add(other)
    db_session.commit()

    db_session.add(PressureTest(log_no="L1", responsible_user_id=seeded_andrei.id))
    db_session.add(PressureTest(log_no="L2", responsible_user_id=other.id))
    db_session.add(PressureTest(log_no="L3"))
    db_session.commit()

    stats = compute_responsibility_stats(db_session, "pressure_tests", seeded_andrei.id)
    assert stats.total_rows == 3
    assert stats.responsible_null == 1
    assert stats.responsible_already_andrei == 1
    assert stats.responsible_assigned_to_other == 1
    assert stats.planned_assignments == 1  # only the NULL row would be touched


@pytest.mark.parametrize("table_name", RESPONSIBILITY_TABLES)
def test_responsibility_stats_works_for_every_target_table(db_session, seeded_andrei, table_name):
    stats = compute_responsibility_stats(db_session, table_name, seeded_andrei.id)
    assert stats.table_name == table_name
    assert stats.total_rows == 0


# --- compute_protected_column_stats(): descriptive only, never a plan --------------

def test_protected_column_stats_counts_null_and_non_null(db_session, seeded_andrei):
    db_session.add(PressureTest(log_no="L1", created_by_user_id=seeded_andrei.id))
    db_session.add(PressureTest(log_no="L2"))
    db_session.commit()

    stats = compute_protected_column_stats(db_session, "pressure_tests", "created_by_user_id")
    assert stats.non_null_count == 1
    assert stats.null_count == 1


def test_every_protected_column_is_queryable(db_session):
    for table_name, column_name in PROTECTED_COLUMNS:
        stats = compute_protected_column_stats(db_session, table_name, column_name)
        assert stats.non_null_count == 0
        assert stats.null_count == 0


def test_audit_events_control_count(db_session):
    db_session.add(AuditEvent(action="something", entity_type="user", entity_id="x"))
    db_session.commit()
    assert compute_audit_events_control_count(db_session) == 1


# --- compute_r2a_field_stats(): gauges/gauge_id/snapshot state ----------------------

def test_r2a_field_stats_all_zero_on_fresh_schema(db_session, seeded_andrei):
    responsibility_stats = [
        compute_responsibility_stats(db_session, t, seeded_andrei.id) for t in RESPONSIBILITY_TABLES
    ]
    r = compute_r2a_field_stats(db_session, responsibility_stats)
    assert r.gauges_row_count == 0
    assert r.gauge_id_filled_count == 0
    assert r.gauge_serial_snapshot_filled_count == 0
    assert r.partial_gauge_pair_count == 0
    assert all(v == 0 for v in r.responsible_already_filled_by_table.values())


def test_r2a_field_stats_detects_nonempty_gauges_table(db_session, seeded_andrei):
    db_session.add(Gauge(serial_number="SN-1"))
    db_session.commit()

    responsibility_stats = [
        compute_responsibility_stats(db_session, t, seeded_andrei.id) for t in RESPONSIBILITY_TABLES
    ]
    r = compute_r2a_field_stats(db_session, responsibility_stats)
    assert r.gauges_row_count == 1


def test_r2a_field_stats_detects_partial_gauge_pair(db_session, seeded_andrei):
    test = PressureTest(log_no="L1")
    db_session.add(test)
    db_session.commit()

    # gauge_id set but snapshot missing - a partial, inconsistent pair
    rev = RevisionModel(pressure_test_id=test.id, revision_id="r1", gauge_id="some-gauge-id")
    db_session.add(rev)
    db_session.commit()

    responsibility_stats = [
        compute_responsibility_stats(db_session, t, seeded_andrei.id) for t in RESPONSIBILITY_TABLES
    ]
    r = compute_r2a_field_stats(db_session, responsibility_stats)
    assert r.partial_gauge_pair_count == 1
    assert r.gauge_id_filled_count == 1
    assert r.gauge_serial_snapshot_filled_count == 0


def test_r2a_field_stats_reflects_already_filled_responsibility(db_session, seeded_andrei):
    db_session.add(PressureTest(log_no="L1", responsible_user_id=seeded_andrei.id))
    db_session.commit()

    responsibility_stats = [
        compute_responsibility_stats(db_session, t, seeded_andrei.id) for t in RESPONSIBILITY_TABLES
    ]
    r = compute_r2a_field_stats(db_session, responsibility_stats)
    assert r.responsible_already_filled_by_table["pressure_tests"] == 1
    assert r.responsible_already_filled_by_table["planned_test_lists"] == 0


# --- pure-Python arithmetic: no DB involved -----------------------------------------

def _wika_nr_stats_from_breakdown(status_breakdown, **overrides):
    total_revisions = sum(b.total for b in status_breakdown)
    nonblank = sum(b.nonblank for b in status_breakdown)
    defaults = dict(
        total_revisions=total_revisions, missing_or_null=0, blank=total_revisions - nonblank,
        nonblank=nonblank, normalized_group_count=0, formatting_conflict_group_count=0,
        status_breakdown=status_breakdown,
        revisions_eligible_for_gauge_link=nonblank, gauges_to_create=0,
    )
    defaults.update(overrides)
    return WikaNrStats(**defaults)


def test_compute_planned_audit_event_counts_sums_responsibility_and_wika_nr():
    responsibility_stats = [
        ResponsibilityStats("pressure_tests", total_rows=5, responsible_null=3,
                             responsible_already_andrei=1, responsible_assigned_to_other=1),
        ResponsibilityStats("planned_test_lists", total_rows=2, responsible_null=2,
                             responsible_already_andrei=0, responsible_assigned_to_other=0),
    ]
    wika_nr_stats = _wika_nr_stats_from_breakdown(
        [StatusWikaNrBreakdown(status="complete", total=8, nonblank=8)],
        normalized_group_count=2, gauges_to_create=2, revisions_eligible_for_gauge_link=8,
    )
    result = compute_planned_audit_event_counts(responsibility_stats, wika_nr_stats)
    assert result.legacy_responsibility_assigned == 3 + 2
    assert result.legacy_gauge_created == 2
    assert result.legacy_gauge_linked == 8


# --- finalized/unknown-status blockers: the corrected status model -----------------

def test_finalized_blocker_confirmed_and_archived_without_gauge_are_blockers():
    wika_nr_stats = _wika_nr_stats_from_breakdown([
        StatusWikaNrBreakdown(status="confirmed", total=3, nonblank=1),  # 2 without gauge
        StatusWikaNrBreakdown(status="archived", total=2, nonblank=0),   # 2 without gauge
        StatusWikaNrBreakdown(status="complete", total=4, nonblank=4),   # 0 without gauge
    ])
    blocker = compute_finalized_without_gauge_blocker(wika_nr_stats)
    assert blocker.finalized_revisions_total == 3 + 2 + 4
    assert blocker.finalized_revisions_without_legacy_gauge == 2 + 2
    assert blocker.without_legacy_gauge_by_status == {"confirmed": 2, "archived": 2, "complete": 0}


def test_finalized_blocker_draft_without_gauge_is_not_a_blocker():
    wika_nr_stats = _wika_nr_stats_from_breakdown([
        StatusWikaNrBreakdown(status="draft", total=5, nonblank=0),  # all blank, but Draft is mutable
    ])
    blocker = compute_finalized_without_gauge_blocker(wika_nr_stats)
    assert blocker.finalized_revisions_total == 0
    assert blocker.finalized_revisions_without_legacy_gauge == 0
    assert blocker.without_legacy_gauge_by_status == {}


def test_unknown_status_blocks_the_plan():
    wika_nr_stats = _wika_nr_stats_from_breakdown([
        StatusWikaNrBreakdown(status="draft", total=2, nonblank=2),
        StatusWikaNrBreakdown(status="pending_review", total=1, nonblank=1),  # not a known status
    ])
    blocker = compute_unknown_status_blocker(wika_nr_stats)
    assert blocker.unknown_status_revision_count == 1
    assert blocker.unknown_statuses == ["pending_review"]


def test_known_statuses_never_trigger_the_unknown_status_blocker():
    wika_nr_stats = _wika_nr_stats_from_breakdown([
        StatusWikaNrBreakdown(status=s, total=1, nonblank=1) for s in ("draft", "complete", "confirmed", "archived")
    ])
    blocker = compute_unknown_status_blocker(wika_nr_stats)
    assert blocker.unknown_status_revision_count == 0
    assert blocker.unknown_statuses == []


def test_finalized_statuses_constant_matches_the_model_comment():
    """services/api/models.py documents TestRevision.status as: draft, complete,
    confirmed, archived. FINALIZED_STATUSES must be exactly the three non-draft ones."""
    assert set(FINALIZED_STATUSES) == {"complete", "confirmed", "archived"}


# --- PlanResult.ok combination logic -------------------------------------------------

def test_plan_result_ok_is_false_when_target_invalid():
    target = TargetCheckResult(
        ardor_env_is_staging=True, dialect_is_postgresql=False,
        current_database_is_expected=False, alembic_head_is_expected=False,
        andrei_count=0, andrei_is_active_admin=False, problems=["database dialect is not PostgreSQL"],
    )
    result = PlanResult(target=target)
    assert result.ok is False


def test_plan_result_ok_is_false_when_business_level_problem_present():
    target = TargetCheckResult(
        ardor_env_is_staging=True, dialect_is_postgresql=True,
        current_database_is_expected=True, alembic_head_is_expected=True,
        andrei_count=1, andrei_is_active_admin=True, problems=[],
    )
    result = PlanResult(target=target, problems=["gauges table is not empty (1 row(s))"])
    assert result.ok is False


def test_plan_result_ok_is_true_when_target_valid_and_no_problems():
    target = TargetCheckResult(
        ardor_env_is_staging=True, dialect_is_postgresql=True,
        current_database_is_expected=True, alembic_head_is_expected=True,
        andrei_count=1, andrei_is_active_admin=True, problems=[],
    )
    result = PlanResult(target=target, problems=[])
    assert result.ok is True


# --- static proof: no write path, no --apply flag, anywhere in the script ----------

_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "plan_r2_legacy_backfill.py")
_FORBIDDEN_TOKENS = (
    "INSERT INTO", "UPDATE ", "DELETE FROM", "TRUNCATE",
    ".add(", ".flush()", ".commit()", ".merge(", ".delete(",
)
_APPLY_FLAG_PATTERN = re.compile(r"""add_argument\(\s*["']--apply["']""")


def test_script_source_contains_no_write_path():
    """No mutating SQL keyword or ORM mutation call may appear anywhere in the script -
    it has exactly one mode (read-only plan)."""
    with open(_SCRIPT_PATH) as f:
        source = f.read()
    found = [tok for tok in _FORBIDDEN_TOKENS if tok in source]
    assert found == [], f"forbidden write-path token(s) found in script source: {found}"


def test_script_source_defines_no_apply_cli_flag():
    """--apply must never exist as an argparse option - the docstring is allowed to
    explain that fact and reference a *future* R2c apply step in prose (e.g. "for a
    future R2c apply"); only an actual add_argument("--apply") definition is forbidden."""
    with open(_SCRIPT_PATH) as f:
        source = f.read()
    assert _APPLY_FLAG_PATTERN.search(source) is None


def test_script_source_never_prints_raw_database_name_or_connection_string():
    """The safe-output requirement: current_database()'s actual return value and
    settings.database_url must never be interpolated into a print() call - only the
    booleans current_database_is_expected / dialect_is_postgresql and the EXPECTED_*
    constants (which are source-code literals, not live-connection data) may appear."""
    with open(_SCRIPT_PATH) as f:
        source = f.read()
    assert "current_database_name" not in "\n".join(
        line for line in source.splitlines() if line.strip().startswith("print(")
    )
    assert "database_url" not in "\n".join(
        line for line in source.splitlines() if line.strip().startswith("print(")
    )
