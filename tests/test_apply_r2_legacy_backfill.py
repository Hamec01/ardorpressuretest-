"""Regression guard for scripts/apply_r2_legacy_backfill.py.

Two tiers, matching the two things that need proving:
  1. Pure logic (outcome separation ABORTED_BEFORE_COMMIT / COMMIT_OUTCOME_UNKNOWN /
     SUCCESS, safe-error-message redaction, PostCheckResult.ok combination logic,
     argparse mode/fingerprint-format validation, call-order proof that table locks are
     acquired before any plan/fingerprint logic runs) - tested here against an isolated
     in-memory SQLite session or, where no DB is needed at all, directly against
     synthetic dataclass instances / monkeypatched collaborator functions. Same pattern
     as every other regression test in this repo.
  2. _acquire_table_locks(), compute_protected_state_fingerprint(),
     compute_plan_fingerprint(), apply_backfill()'s real mutation/postcondition logic,
     run_post_check_logic(), and _verify_r2c_audit_events_exact() all depend on
     PostgreSQL-only syntax (LOCK TABLE, jsonb ->>/::jsonb operators, entity_id =
     ANY(:array)) and are deliberately NOT exercised here - they are covered separately
     against a throwaway PostgreSQL instance upgraded to 2327325e8143 with synthetic
     data sized to match the real staging apply, including: dry-run-does-not-mutate,
     successful-apply-shape, repeat-apply-refuses, wrong-fingerprint-refuses (both
     fingerprints independently), plan-drift-refuses, protected-UUID-swap-at-identical-
     counts-detected, metadata_json-change-without-normalized-change-detected, serial
     case/whitespace-only-change-detected, andrei-id-change-detected, already-Andrei-
     responsible-before-apply-refuses, post-check-with-responsible-set-to-another-admin-
     fails, UPDATE-rowcount-0-or-2-rolls-back, existing-gauge/snapshot-pair-refuses-
     without-overwrite, extra-rogue-audit-event-with-wrong-actor/user_id/details-fails-
     post-check, missing-plus-duplicate-entity-id-at-unchanged-total-fails-post-check-
     and-rolls-back (one expected entity_id has no event, another has two, so the
     aggregate COUNT(*) alone would not move), extra-details_json-key-alongside-the-
     correct-reason-fails (details_json must match the expected object exactly, not just
     its 'reason' value), gauge-linked-to-a-non-eligible-revision-fails, deactivated-
     Gauge-fails, correct-gauge-count-but-wrong-serial-in-the-set-fails,
     dry-run-withholds-both-fingerprints-when-PLAN_OK-is-false,
     dry-run-withholds-both-fingerprints-when-a-preexisting-R2c-audit-event-exists,
     JSON-null-wika_nr-with-a-gauge-pair-set-is-still-caught-as-noneligible (the
     NULL-swallowing complement bug: NONBLANK_WIKA_NR_PREDICATE evaluates to SQL NULL,
     not FALSE, for `"wika_nr": null`, and a naive `NOT (<predicate>)` complement would
     have silently excluded that same revision from the noneligible check too),
     missing-key/JSON-null/blank/whitespace-only wika_nr all independently proven
     noneligible, Gauge-deactivated-after-creation-but-before-commit-postcondition-
     rolls-back-the-whole-apply, wrong-Gauge-serial-at-the-same-count-before-commit-
     rolls-back-the-whole-apply, gauge-pair-assigned-to-a-noneligible-revision-
     (including wika_nr: null) before-commit-rolls-back-the-whole-apply (not merely
     caught later by a standalone --post-check - compute_gauge_invariant_stats() is
     checked inside apply_backfill() itself, before commit, using the exact same
     helper run_post_check_logic() uses, so the two can never diverge), pre-commit-
     failure-fully-rolls-back, two-connection concurrency (locks block a concurrent
     writer until commit/rollback, then release), and no-partial-backfill-on-timeout-
     or-injected-failure (a manual CLI/psql verification, not a pytest module, since it
     needs a real Postgres server this test suite does not have access to).
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
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.database import Base
from services.api.models import User

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.apply_r2_legacy_backfill import (  # noqa: E402
    ACTOR_LABEL,
    ApplyOutcome,
    ApplyPostconditionError,
    ApplyResult,
    ApplyTargetError,
    FingerprintMismatchError,
    PostCheckResult,
    main as apply_main,
    run_apply,
    _fingerprint_arg_type,
    _safe_failure_message,
)
import scripts.apply_r2_legacy_backfill as apply_module

_VALID_FP_A = "a" * 64
_VALID_FP_B = "b" * 64


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


# --- run_apply(): the three outcomes must never be conflated ------------------------

def test_run_apply_success_returns_success_outcome_and_summary(db_session, monkeypatch):
    expected_summary = ApplyResult(
        responsibility_assigned_by_table={"pressure_tests": 34, "planned_test_lists": 7, "pressure_test_records": 3},
        gauges_created=1, revisions_linked=40, audit_events_added=85,
    )

    def fake_apply_backfill(db, environment, expected_plan_fingerprint, expected_protected_state_fingerprint):
        return expected_summary

    monkeypatch.setattr(apply_module, "apply_backfill", fake_apply_backfill)

    result = run_apply(db_session, "staging", _VALID_FP_A, _VALID_FP_B)

    assert result.outcome is ApplyOutcome.SUCCESS
    assert result.safe_message is None
    assert result.summary is expected_summary


def test_run_apply_aborted_before_commit_is_reported_and_rolled_back(db_session, monkeypatch):
    rollback_called = {"value": False}
    real_rollback = db_session.rollback

    def spy_rollback():
        rollback_called["value"] = True
        real_rollback()

    monkeypatch.setattr(db_session, "rollback", spy_rollback)

    def failing_apply_backfill(db, environment, expected_plan_fingerprint, expected_protected_state_fingerprint):
        raise ApplyTargetError("simulated pre-commit failure, safe text only")

    monkeypatch.setattr(apply_module, "apply_backfill", failing_apply_backfill)

    result = run_apply(db_session, "staging", _VALID_FP_A, _VALID_FP_B)

    assert result.outcome is ApplyOutcome.ABORTED_BEFORE_COMMIT
    assert "simulated pre-commit failure" in result.safe_message
    assert result.summary is None
    assert rollback_called["value"] is True


def test_run_apply_commit_failure_is_never_reported_as_rollback_or_success(db_session, monkeypatch):
    def fake_apply_backfill(db, environment, expected_plan_fingerprint, expected_protected_state_fingerprint):
        return ApplyResult(
            responsibility_assigned_by_table={"pressure_tests": 1, "planned_test_lists": 0, "pressure_test_records": 0},
            gauges_created=0, revisions_linked=0, audit_events_added=1,
        )

    monkeypatch.setattr(apply_module, "apply_backfill", fake_apply_backfill)

    rollback_called = {"value": False}

    def spy_rollback():
        rollback_called["value"] = True

    monkeypatch.setattr(db_session, "rollback", spy_rollback)

    def failing_commit():
        raise OperationalError(
            "COMMIT", {}, Exception("connection lost mid-commit, outcome unknown server-side"),
        )

    monkeypatch.setattr(db_session, "commit", failing_commit)

    result = run_apply(db_session, "staging", _VALID_FP_A, _VALID_FP_B)

    assert result.outcome is ApplyOutcome.COMMIT_OUTCOME_UNKNOWN
    assert result.outcome is not ApplyOutcome.ABORTED_BEFORE_COMMIT
    assert result.outcome is not ApplyOutcome.SUCCESS
    assert "connection lost" not in result.safe_message
    assert "outcome unknown server-side" not in result.safe_message
    assert result.safe_message == "OperationalError (details withheld: may contain SQL text/parameters)"
    # Crucially: run_apply() must never call rollback() on a commit-time failure - that
    # would falsely claim the (possibly-already-reached-the-server) commit was undone.
    assert rollback_called["value"] is False


def test_lock_timeout_is_aborted_before_commit_with_full_rollback_and_safe_message(db_session, monkeypatch):
    """A lock_timeout failure is just another exception raised before commit - it needs
    no special-case handling and must go through the exact same ABORTED_BEFORE_COMMIT /
    rollback / redacted-message path as any other pre-commit failure."""
    rollback_called = {"value": False}
    real_rollback = db_session.rollback

    def spy_rollback():
        rollback_called["value"] = True
        real_rollback()

    monkeypatch.setattr(db_session, "rollback", spy_rollback)

    def failing_locks(db):
        raise OperationalError(
            'LOCK TABLE "pressure_tests" IN SHARE ROW EXCLUSIVE MODE',
            {},
            Exception("canceling statement due to lock timeout"),
        )

    monkeypatch.setattr(apply_module, "_acquire_table_locks", failing_locks)

    result = run_apply(db_session, "staging", _VALID_FP_A, _VALID_FP_B)

    assert result.outcome is ApplyOutcome.ABORTED_BEFORE_COMMIT
    assert "lock timeout" not in result.safe_message
    assert "LOCK TABLE" not in result.safe_message
    assert result.safe_message == "OperationalError (details withheld: may contain SQL text/parameters)"
    assert rollback_called["value"] is True


# --- apply_backfill(): locks must be acquired before any plan/fingerprint logic -----

def test_locks_are_acquired_before_run_plan_and_fingerprints(db_session, monkeypatch):
    call_order = []

    def fake_locks(db):
        call_order.append("locks")

    def fake_preexisting(db):
        call_order.append("preexisting_check")
        return 0

    def fake_run_plan(db, environment):
        call_order.append("run_plan")
        target = type("FakeTarget", (), {"ok": True, "problems": []})()
        return type("FakePlan", (), {"ok": True, "target": target, "problems": []})()

    def fake_compute_both(db):
        call_order.append("fingerprints")
        # Deliberately mismatched so apply_backfill() stops right here, cleanly, with
        # FingerprintMismatchError - before any mutation, and before the SQLite session
        # would otherwise hit Postgres-only jsonb syntax in the real query text.
        return "mismatched_plan_fp", "mismatched_protected_fp", "andrei-id"

    monkeypatch.setattr(apply_module, "_acquire_table_locks", fake_locks)
    monkeypatch.setattr(apply_module, "_check_no_preexisting_r2c_audit_events", fake_preexisting)
    monkeypatch.setattr(apply_module, "run_plan", fake_run_plan)
    monkeypatch.setattr(apply_module, "_compute_both_fingerprints", fake_compute_both)

    with pytest.raises(FingerprintMismatchError):
        apply_module.apply_backfill(db_session, "staging", _VALID_FP_A, _VALID_FP_B)

    assert call_order == ["locks", "preexisting_check", "run_plan", "fingerprints"]


def test_preexisting_r2c_audit_events_block_apply_even_before_run_plan(db_session, monkeypatch):
    call_order = []

    def fake_locks(db):
        call_order.append("locks")

    def fake_preexisting(db):
        call_order.append("preexisting_check")
        return 2  # non-zero: must stop here, before run_plan is ever called

    def fake_run_plan(db, environment):
        call_order.append("run_plan")
        raise AssertionError("run_plan must not be called when preexisting R2c audit events are found")

    monkeypatch.setattr(apply_module, "_acquire_table_locks", fake_locks)
    monkeypatch.setattr(apply_module, "_check_no_preexisting_r2c_audit_events", fake_preexisting)
    monkeypatch.setattr(apply_module, "run_plan", fake_run_plan)

    with pytest.raises(ApplyTargetError, match="already use one of the three reserved"):
        apply_module.apply_backfill(db_session, "staging", _VALID_FP_A, _VALID_FP_B)

    assert call_order == ["locks", "preexisting_check"]


def test_plan_not_ok_refuses_before_fingerprints_are_even_computed(db_session, monkeypatch):
    call_order = []

    monkeypatch.setattr(apply_module, "_acquire_table_locks", lambda db: call_order.append("locks"))
    monkeypatch.setattr(apply_module, "_check_no_preexisting_r2c_audit_events", lambda db: 0)

    def fake_run_plan(db, environment):
        call_order.append("run_plan")
        target = type("FakeTarget", (), {"ok": True, "problems": []})()
        return type("FakePlan", (), {"ok": False, "target": target, "problems": ["synthetic PLAN_OK=False reason"]})()

    def fake_compute_both(db):
        call_order.append("fingerprints")
        raise AssertionError("fingerprints must not be computed when PLAN_OK is already False")

    monkeypatch.setattr(apply_module, "run_plan", fake_run_plan)
    monkeypatch.setattr(apply_module, "_compute_both_fingerprints", fake_compute_both)

    with pytest.raises(ApplyTargetError, match="synthetic PLAN_OK=False reason"):
        apply_module.apply_backfill(db_session, "staging", _VALID_FP_A, _VALID_FP_B)

    assert call_order == ["locks", "run_plan"]


def test_protected_state_fingerprint_is_checked_before_plan_fingerprint(db_session, monkeypatch):
    """Both are required, but the protected-state fingerprint (proving nothing outside
    this operation's intended scope has drifted) is the stricter, more fundamental
    guarantee - it is checked first, so a protected-state mismatch is never masked by
    reporting a generic plan-fingerprint mismatch instead."""
    monkeypatch.setattr(apply_module, "_acquire_table_locks", lambda db: None)
    monkeypatch.setattr(apply_module, "_check_no_preexisting_r2c_audit_events", lambda db: 0)

    def fake_run_plan(db, environment):
        target = type("FakeTarget", (), {"ok": True, "problems": []})()
        return type("FakePlan", (), {"ok": True, "target": target, "problems": []})()

    monkeypatch.setattr(apply_module, "run_plan", fake_run_plan)
    monkeypatch.setattr(
        apply_module, "_compute_both_fingerprints",
        lambda db: ("also_mismatched_plan_fp", "mismatched_protected_fp", "andrei-id"),
    )

    with pytest.raises(FingerprintMismatchError, match="protected-state fingerprint mismatch"):
        apply_module.apply_backfill(db_session, "staging", _VALID_FP_A, _VALID_FP_B)


# --- _safe_failure_message(): controlled types pass through, everything else redacted

def test_safe_failure_message_passes_through_known_error_types_unmodified():
    err = ApplyTargetError("Refusing to apply: PLAN_OK is False. Reasons: gauges table is not empty (1 row(s))")
    assert _safe_failure_message(err) == str(err)

    fp_err = FingerprintMismatchError("Refusing to apply: plan fingerprint mismatch expected=aaa actual=bbb")
    assert _safe_failure_message(fp_err) == str(fp_err)

    pc_err = ApplyPostconditionError("Post-check failed: 'pressure_tests' still has 3 row(s) with NULL responsible_user_id.")
    assert _safe_failure_message(pc_err) == str(pc_err)


def test_safe_failure_message_redacts_unknown_exception_types():
    err = OperationalError(
        "UPDATE pressure_tests SET responsible_user_id = %(andrei_id)s",
        {"andrei_id": "leaked-uuid-should-not-appear"},
        Exception("simulated driver failure"),
    )
    safe = _safe_failure_message(err)
    assert "leaked-uuid-should-not-appear" not in safe
    assert "UPDATE pressure_tests" not in safe
    assert safe == "OperationalError (details withheld: may contain SQL text/parameters)"


# --- PostCheckResult.ok: every sub-condition must independently gate the result -----

def _ok_post_check_result(**overrides):
    defaults = dict(
        responsibility_is_exactly_andrei_by_table={
            "pressure_tests": True, "planned_test_lists": True, "pressure_test_records": True,
        },
        gauge_group_count=1, gauges_row_count=1, gauge_groups_match_gauges=True,
        partial_gauge_pair_count=0, inconsistent_link_count=0,
        unexpected_noneligible_gauge_pair_count=0,
        inactive_gauge_count=0,
        gauge_serial_set_matches=True,
        audit_problems=[],
        protected_state_fingerprint_matches=True,
        protected_column_stats=[],
    )
    defaults.update(overrides)
    return PostCheckResult(**defaults)


def test_post_check_ok_true_when_everything_consistent():
    assert _ok_post_check_result().ok is True


@pytest.mark.parametrize("field,value", [
    (
        "responsibility_is_exactly_andrei_by_table",
        # Models "post-check with responsible set to another Admin": the row is no
        # longer NULL (an earlier null-count-only check would have missed this), but it
        # is not exactly andrei.sakki's id either.
        {"pressure_tests": False, "planned_test_lists": True, "pressure_test_records": True},
    ),
    ("gauge_groups_match_gauges", False),
    ("partial_gauge_pair_count", 1),
    ("inconsistent_link_count", 1),
    # A Gauge linked to a revision with no usable legacy wika_nr - this backfill was
    # never supposed to touch that revision at all.
    ("unexpected_noneligible_gauge_pair_count", 1),
    # A Gauge this backfill created (or should have created) was deactivated afterward.
    ("inactive_gauge_count", 1),
    # Same gauge COUNT as expected, but the exact set of serial numbers doesn't match -
    # e.g. one gauge's serial belongs to the wrong normalized group.
    ("gauge_serial_set_matches", False),
    ("audit_problems", ["legacy_gauge_linked/test_revision: 1 expected entity id(s) have no fully-correct event"]),
    ("protected_state_fingerprint_matches", False),
])
def test_post_check_ok_false_when_any_single_condition_fails(field, value):
    result = _ok_post_check_result(**{field: value})
    assert result.ok is False


# --- _fingerprint_arg_type(): the argparse-level 64-hex validator ------------------

@pytest.mark.parametrize("value", [
    "a" * 64,
    "0123456789abcdef" * 4,
])
def test_fingerprint_arg_type_accepts_valid_hex64(value):
    assert _fingerprint_arg_type(value) == value


@pytest.mark.parametrize("value", [
    "",
    "a" * 63,
    "a" * 65,
    "A" * 64,  # uppercase hex is rejected - the script's own output is always lowercase
    "g" * 64,  # not a hex digit
    "not-a-fingerprint-at-all",
    "a" * 64 + "\n",
])
def test_fingerprint_arg_type_rejects_everything_else(value):
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        _fingerprint_arg_type(value)


# --- argparse: mode/fingerprint requirements, all enforced before any DB connection -

def _run_main_with_args(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["apply_r2_legacy_backfill.py"] + args)


def test_apply_without_any_fingerprint_is_rejected_before_any_db_call(monkeypatch, capsys):
    _run_main_with_args(monkeypatch, ["--apply"])
    with pytest.raises(SystemExit) as exc_info:
        apply_main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--expected-plan-fingerprint" in captured.err


def test_apply_with_only_plan_fingerprint_is_rejected(monkeypatch, capsys):
    _run_main_with_args(monkeypatch, ["--apply", "--expected-plan-fingerprint", _VALID_FP_A])
    with pytest.raises(SystemExit) as exc_info:
        apply_main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--expected-protected-state-fingerprint" in captured.err


def test_apply_with_only_protected_state_fingerprint_is_rejected(monkeypatch, capsys):
    _run_main_with_args(monkeypatch, ["--apply", "--expected-protected-state-fingerprint", _VALID_FP_B])
    with pytest.raises(SystemExit) as exc_info:
        apply_main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--expected-plan-fingerprint" in captured.err


def test_post_check_without_protected_state_fingerprint_is_rejected(monkeypatch, capsys):
    _run_main_with_args(monkeypatch, ["--post-check"])
    with pytest.raises(SystemExit) as exc_info:
        apply_main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--expected-protected-state-fingerprint" in captured.err


def test_plan_fingerprint_without_apply_is_rejected(monkeypatch, capsys):
    _run_main_with_args(monkeypatch, ["--expected-plan-fingerprint", _VALID_FP_A])
    with pytest.raises(SystemExit) as exc_info:
        apply_main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--expected-plan-fingerprint" in captured.err


def test_protected_state_fingerprint_without_apply_or_post_check_is_rejected(monkeypatch, capsys):
    _run_main_with_args(monkeypatch, ["--expected-protected-state-fingerprint", _VALID_FP_B])
    with pytest.raises(SystemExit) as exc_info:
        apply_main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--expected-protected-state-fingerprint" in captured.err


def test_apply_and_post_check_together_is_rejected(monkeypatch, capsys):
    _run_main_with_args(monkeypatch, [
        "--apply", "--post-check",
        "--expected-plan-fingerprint", _VALID_FP_A,
        "--expected-protected-state-fingerprint", _VALID_FP_B,
    ])
    with pytest.raises(SystemExit) as exc_info:
        apply_main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "not allowed with argument" in captured.err or "mutually exclusive" in captured.err.lower()


def test_malformed_fingerprint_is_rejected_before_any_db_connection(monkeypatch, capsys):
    """The type= validator runs inside parser.parse_args(), which main() calls before
    it does anything else - including before create_engine() is ever reached. A
    malformed fingerprint must never get far enough to open a database connection."""
    def fake_create_engine(*a, **kw):
        raise AssertionError("create_engine must not be called before argparse validates fingerprint format")

    monkeypatch.setattr(apply_module, "create_engine", fake_create_engine)

    _run_main_with_args(monkeypatch, [
        "--apply",
        "--expected-plan-fingerprint", "not-a-valid-hex-fingerprint",
        "--expected-protected-state-fingerprint", _VALID_FP_B,
    ])
    with pytest.raises(SystemExit) as exc_info:
        apply_main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "64 lowercase hex" in captured.err


def test_malformed_protected_state_fingerprint_on_post_check_is_rejected_before_db(monkeypatch, capsys):
    def fake_create_engine(*a, **kw):
        raise AssertionError("create_engine must not be called before argparse validates fingerprint format")

    monkeypatch.setattr(apply_module, "create_engine", fake_create_engine)

    _run_main_with_args(monkeypatch, ["--post-check", "--expected-protected-state-fingerprint", "short"])
    with pytest.raises(SystemExit) as exc_info:
        apply_main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "64 lowercase hex" in captured.err


# --- static proof: audit user_id is never faked, actor_name is a fixed safe label ---

_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "apply_r2_legacy_backfill.py")
_AUDIT_EVENT_USER_ID_KWARG_PATTERN = re.compile(r"AuditEvent\([^)]*\buser_id\s*=")


def test_audit_events_never_set_user_id():
    """AuditEvent.user_id means 'the human who submitted this request as themselves' -
    a script-driven bulk operation must never fake it as andrei's id or anyone else's.
    Every AuditEvent(...) construction in this script must omit user_id entirely,
    leaving it NULL, and use actor_name=ACTOR_LABEL instead."""
    with open(_SCRIPT_PATH) as f:
        source = f.read()
    assert _AUDIT_EVENT_USER_ID_KWARG_PATTERN.search(source) is None
    assert ACTOR_LABEL != "andrei.sakki"
    assert "@" not in ACTOR_LABEL  # not an email/real identity, just a fixed safe label


def test_actor_label_used_consistently_for_every_audit_event():
    with open(_SCRIPT_PATH) as f:
        source = f.read()
    audit_event_blocks = re.findall(r"AuditEvent\(.*?\)\)", source, re.DOTALL)
    assert len(audit_event_blocks) >= 3  # responsibility, gauge_created, gauge_linked
    for block in audit_event_blocks:
        assert "actor_name=ACTOR_LABEL" in block


# --- static proof: every write is guarded by an explicit precondition + rowcount ----

def test_every_update_statement_has_an_explicit_null_precondition_and_rowcount_guard():
    """Both mutating UPDATE statements (responsible_user_id assignment, gauge link) must
    scope their WHERE clause with the exact precondition being relied upon (never
    touching a row that turns out to already be set), and the code immediately after
    each db.execute(...) of an UPDATE must check .rowcount before proceeding."""
    with open(_SCRIPT_PATH) as f:
        source = f.read()

    assert "WHERE id = :row_id AND responsible_user_id IS NULL" in source
    assert "WHERE id = :rev_id AND gauge_id IS NULL AND gauge_serial_snapshot IS NULL" in source
    assert source.count("result.rowcount != 1") == 2


def test_locks_are_the_first_statement_in_acquire_table_locks_and_cover_all_required_tables():
    with open(_SCRIPT_PATH) as f:
        source = f.read()
    assert "SET LOCAL lock_timeout" in source
    for table in (
        "alembic_version", "users", "pressure_tests", "planned_test_lists",
        "pressure_test_records", "test_revisions", "gauges", "audit_events",
    ):
        assert f'LOCK TABLE "{table}" IN SHARE ROW EXCLUSIVE MODE' in source or table in apply_module.LOCK_TABLES_IN_ORDER
    assert list(apply_module.LOCK_TABLES_IN_ORDER) == [
        "alembic_version", "users", "pressure_tests", "planned_test_lists",
        "pressure_test_records", "test_revisions", "gauges", "audit_events",
    ]


def test_dry_run_fingerprint_gate_requires_both_ok_and_zero_preexisting():
    """Static proof that run_dry_run() only prints PLAN_FINGERPRINT/
    PROTECTED_STATE_FINGERPRINT under the combined gate (PLAN_OK True AND preexisting
    R2c-action audit events == 0), and otherwise prints an explicit
    FINGERPRINTS_NOT_COMPUTED notice instead of silently omitting them. run_dry_run()
    itself cannot run in this SQLite tier (`BEGIN TRANSACTION READ ONLY` is
    PostgreSQL-only syntax) - the two real scenarios (PLAN_OK=False, and preexisting R2c
    audit events present) are exercised against a real Postgres server in the
    throwaway-Postgres tier."""
    with open(_SCRIPT_PATH) as f:
        source = f.read()
    assert "if ok and preexisting == 0:" in source
    assert "FINGERPRINTS_NOT_COMPUTED" in source


def test_details_json_verification_requires_exact_equality_not_substring():
    """Static proof that audit-event verification compares details_json for exact
    equality (an extra/renamed/changed key must be caught), not merely a reason
    substring - the old `details_json->>'reason' = :reason` pattern must be gone."""
    with open(_SCRIPT_PATH) as f:
        source = f.read()
    assert "details_json->>'reason' = :reason" not in source
    assert "details_json::jsonb = (:expected_details_json)::jsonb" in source


def test_noneligible_complement_is_null_safe():
    """Static proof that the 'noneligible' complement of NONBLANK_WIKA_NR_PREDICATE
    coalesces to boolean false before negating, so a revision whose metadata_json has
    `"wika_nr": null` (a JSON null value, not a missing key or a blank string) - where
    NONBLANK_WIKA_NR_PREDICATE itself evaluates to SQL NULL, not just FALSE, because
    `->>'wika_nr'` on a JSON null returns SQL NULL - is still unambiguously counted as
    noneligible. The old buggy pattern (`NOT (<predicate>)` with no COALESCE) must be
    gone: `NOT NULL` is NULL, not TRUE, so it would silently exclude that same revision
    from the noneligible check too, letting a wrongly-set gauge pair on it go
    undetected by either check. The real JSON-null behavior itself is exercised against
    a real Postgres server in the throwaway-Postgres tier."""
    with open(_SCRIPT_PATH) as f:
        source = f.read()
    assert "NOT COALESCE((" in source and "), false)" in source
    assert "WHERE NOT ({NONBLANK_WIKA_NR_PREDICATE})" not in source
    assert 'WHERE NOT (action = ANY(:actions))' in source  # unrelated NOT usage, untouched


def test_gauge_invariants_computed_by_one_shared_helper_not_duplicated():
    """Static proof that both apply_backfill()'s pre-commit postcondition and the
    standalone run_post_check_logic() call the exact same compute_gauge_invariant_stats()
    helper, rather than maintaining two independently-hand-written copies of the same
    SQL that could quietly drift apart from each other over time."""
    with open(_SCRIPT_PATH) as f:
        source = f.read()
    assert source.count("compute_gauge_invariant_stats(db)") == 2
    assert source.count("gauge_stats = compute_gauge_invariant_stats(db)") == 2
    # The old ad hoc per-function gauge-count/inconsistent-pair SQL must be gone from
    # apply_backfill()'s own body - it must rely on the shared helper instead.
    assert "expected {len(group_rows)} Gauge row(s), found" not in source
    # apply_backfill() must actually check the result and raise on failure, not merely
    # compute it - see the throwaway-Postgres tier for the corresponding dynamic proof
    # (compute_gauge_invariant_stats() needs real PostgreSQL jsonb syntax to run).
    assert "if not gauge_stats.ok:" in source
    assert "gauge_stats.safe_problem_summary()" in source
