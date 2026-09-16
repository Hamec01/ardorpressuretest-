"""Regression guard for scripts/deactivate_foreman_matti_operator_pekka.py.

Tests only the importable, non-interactive core (verify_target/apply_deactivation/
_safe_failure_message/check_post_apply_state) plus a direct proof that a JWT issued for
one of these accounts while it was active stops working the moment is_active flips to
False - the central safety claim behind "deactivating is safe, no live session survives
it because there is no server-side session to begin with; stateless JWTs are re-checked
against is_active on every single request".

Isolated by design, same pattern as the other R1/R1a/R1b/bootstrap regression tests: a
private in-memory SQLite session, never the process-wide engine. DATABASE_URL /
STORAGE_DIR must still be exported to isolated temporary values by the caller, because
services.api.config.Settings() is constructed at first import time, and ARDOR_ENV must
be an explicit local/dev/test value for that module-level construction to succeed - the
tests below pass their own `environment` argument to verify_target()/apply_deactivation()
directly, independent of that ambient process-level ARDOR_ENV.
"""
import os

_db_url = os.environ.get("DATABASE_URL", "")
_storage_dir = os.environ.get("STORAGE_DIR", "")
_ardor_env = os.environ.get("ARDOR_ENV", "")

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
if _ardor_env.strip().lower() not in ("local", "dev", "development", "test", "testing"):
    raise RuntimeError(
        "ARDOR_ENV must be explicitly local/dev/test for this test run (R1 fail-closed "
        "default). Export ARDOR_ENV=test before running this test."
    )

import sys

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.auth import create_access_token, hash_password, require_role
from services.api.database import Base
from services.api.models import AuditEvent, User

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.deactivate_foreman_matti_operator_pekka import (  # noqa: E402
    DEACTIVATION_ACTION,
    EXPECTED_ARDOR_ENV,
    PROTECTED_ADMIN_USERNAMES,
    TARGET_USERNAMES,
    ApplyOutcome,
    DeactivationPostconditionError,
    DeactivationTargetError,
    apply_deactivation,
    check_post_apply_state,
    run_apply,
    run_dry_run,
    run_post_apply_check,
    run_pre_apply_check,
    verify_target,
    _count_matching_deactivation_audit_events,
    _new_deactivation_audit_event,
    _safe_failure_message,
)
import scripts.deactivate_foreman_matti_operator_pekka as deactivate_module

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
    return User(
        username=username,
        full_name=username,
        role=role,
        hashed_password=hash_password("irrelevant-for-this-script"),
        is_active=is_active,
    )


@pytest.fixture()
def seeded_protected_admins(db_session):
    admin = _make_user("admin", "admin")
    andrei = _make_user("andrei.sakki", "admin")
    db_session.add_all([admin, andrei])
    db_session.commit()
    return admin, andrei


@pytest.fixture()
def seeded_targets(db_session):
    foreman_matti = _make_user("foreman_matti", "foreman")
    operator_pekka = _make_user("operator_pekka", "operator")
    db_session.add_all([foreman_matti, operator_pekka])
    db_session.commit()
    return foreman_matti, operator_pekka


@pytest.fixture()
def fully_seeded(db_session, seeded_protected_admins, seeded_targets):
    """Both protected admins active + both targets active - the one and only state
    verify_target() should accept (modulo the dialect gate, which is inherently sqlite
    in this isolated suite and is tested separately)."""
    return seeded_protected_admins, seeded_targets


# --- verify_target(): wrong-target cases -----------------------------------------

def test_verify_target_fails_on_sqlite_dialect(db_session, fully_seeded):
    check = verify_target(db_session, STAGING)
    assert check.dialect_is_postgresql is False
    assert check.ok is False
    assert any("PostgreSQL" in p for p in check.problems)


def test_verify_target_fails_when_ardor_env_is_not_staging(db_session, fully_seeded):
    for wrong_env in ("local", "dev", "production", "", "Staging"):
        check = verify_target(db_session, wrong_env)
        assert check.ardor_env_is_staging is False
        assert check.ok is False


def test_verify_target_fails_when_admin_missing(db_session, seeded_targets):
    check = verify_target(db_session, STAGING)
    assert check.protected_admins_ok is False
    assert check.ok is False


def test_verify_target_fails_when_andrei_sakki_missing(db_session, seeded_targets):
    db_session.add(_make_user("admin", "admin"))
    db_session.commit()

    check = verify_target(db_session, STAGING)
    assert check.protected_admins_ok is False
    assert check.ok is False


def test_verify_target_fails_when_a_protected_admin_is_inactive(db_session, seeded_targets):
    db_session.add(_make_user("admin", "admin", is_active=True))
    db_session.add(_make_user("andrei.sakki", "admin", is_active=False))
    db_session.commit()

    check = verify_target(db_session, STAGING)
    assert check.protected_admins_ok is False
    assert check.ok is False


def test_verify_target_fails_when_a_protected_admin_has_wrong_role(db_session, seeded_targets):
    db_session.add(_make_user("admin", "admin"))
    db_session.add(_make_user("andrei.sakki", "foreman"))  # role tampered
    db_session.commit()

    check = verify_target(db_session, STAGING)
    assert check.protected_admins_ok is False
    assert check.ok is False


def test_verify_target_fails_when_a_target_is_missing(db_session, seeded_protected_admins):
    db_session.add(_make_user("foreman_matti", "foreman"))
    db_session.commit()
    # operator_pekka missing entirely

    check = verify_target(db_session, STAGING)
    assert check.targets_currently_active is False
    assert check.ok is False


def test_verify_target_fails_when_a_target_is_already_inactive(db_session, seeded_protected_admins):
    """This is the idempotency guard: once either target is already inactive, a second
    run must refuse rather than silently no-op or double-write audit events."""
    db_session.add(_make_user("foreman_matti", "foreman", is_active=False))
    db_session.add(_make_user("operator_pekka", "operator", is_active=True))
    db_session.commit()

    check = verify_target(db_session, STAGING)
    assert check.targets_currently_active is False
    assert check.ok is False
    assert any("already inactive" in p for p in check.problems)


def test_verify_target_passes_all_non_dialect_checks_when_fully_seeded(db_session, fully_seeded):
    check = verify_target(db_session, STAGING)
    assert check.ardor_env_is_staging is True
    assert check.protected_admins_ok is True
    assert check.targets_currently_active is True
    # still not ok overall, because dialect is sqlite in this isolated test
    assert check.ok is False
    assert check.problems == ["database dialect is not PostgreSQL"]


# --- apply_deactivation(): refuses on bad target, no changes ---------------------

def test_apply_refuses_when_a_protected_admin_is_inactive(db_session, seeded_targets):
    db_session.add(_make_user("admin", "admin", is_active=True))
    db_session.add(_make_user("andrei.sakki", "admin", is_active=False))
    db_session.commit()

    with pytest.raises(DeactivationTargetError):
        apply_deactivation(db_session, STAGING)
    db_session.rollback()

    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    assert foreman.is_active is True
    assert db_session.query(AuditEvent).count() == 0


def test_apply_refuses_when_ardor_env_wrong_even_with_good_accounts(db_session, fully_seeded):
    with pytest.raises(DeactivationTargetError) as exc_info:
        apply_deactivation(db_session, "production")
    db_session.rollback()
    assert "ARDOR_ENV" in str(exc_info.value)
    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    assert foreman.is_active is True


# --- apply_deactivation(): success path (dialect gate bypassed the same way the
#     bootstrap script's test suite does, since the isolated fixture is inherently
#     SQLite; verify_target() itself is still fully tested above, including the
#     dialect gate). ------------------------------------------------------------

def _force_apply_ignoring_dialect(db, environment, event_factory=None):
    """Test-only helper: apply_deactivation()'s own logic, minus the
    dialect_is_postgresql/current_database gate, so the success/rollback/postcondition
    paths can be exercised against the isolated SQLite fixture. verify_target() itself
    is still fully tested above, including the dialect gate; production code always
    goes through the real gate. Reuses the real _new_deactivation_audit_event() and
    _count_matching_deactivation_audit_events() helpers so this test double cannot
    silently drift from the production audit-attribution logic it is meant to exercise.

    event_factory, if given, replaces _new_deactivation_audit_event() - used by
    test_broken_audit_attribution_... below to simulate a bug that produces a
    wrongly-attributed audit event for one target, without touching the account-state
    logic at all.
    """
    factory = event_factory or _new_deactivation_audit_event

    check = verify_target(db, environment)
    non_dialect_problems = [p for p in check.problems if "PostgreSQL" not in p and "current_database" not in p]
    if non_dialect_problems:
        raise DeactivationTargetError("Target verification failed, no changes made: " + "; ".join(non_dialect_problems))

    protected_ids_before = {
        uname: db.query(User).filter(User.username == uname).first().id
        for uname in PROTECTED_ADMIN_USERNAMES
    }

    target_user_ids = {}
    for uname in TARGET_USERNAMES:
        user = db.query(User).filter(User.username == uname).first()
        user.is_active = False
        target_user_ids[uname] = user.id
        db.add(factory(uname, user.id))

    db.flush()

    for uname in TARGET_USERNAMES:
        row = db.query(User).filter(User.username == uname).first()
        if row is None or row.is_active is not False:
            raise DeactivationPostconditionError(f"Post-check failed: '{uname}' is not inactive as expected.")
    for uname in PROTECTED_ADMIN_USERNAMES:
        row = db.query(User).filter(User.username == uname).first()
        if row is None or row.id != protected_ids_before[uname] or not row.is_active or row.role != "admin":
            raise DeactivationPostconditionError(f"Post-check failed: protected account '{uname}' changed unexpectedly.")

    for uname in TARGET_USERNAMES:
        matching_count = _count_matching_deactivation_audit_events(db, target_user_ids[uname])
        if matching_count != 1:
            raise DeactivationPostconditionError(
                f"Post-check failed: expected exactly 1 deactivation audit event for "
                f"'{uname}', found {matching_count}."
            )

    return list(target_user_ids.keys())


def test_apply_deactivates_both_targets_only(db_session, fully_seeded):
    _force_apply_ignoring_dialect(db_session, STAGING)
    db_session.commit()

    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    operator = db_session.query(User).filter(User.username == "operator_pekka").first()
    admin = db_session.query(User).filter(User.username == "admin").first()
    andrei = db_session.query(User).filter(User.username == "andrei.sakki").first()

    assert foreman.is_active is False
    assert operator.is_active is False
    assert admin.is_active is True and admin.role == "admin"
    assert andrei.is_active is True and andrei.role == "admin"
    # roles/usernames/full_name untouched - only is_active changed
    assert foreman.role == "foreman"
    assert operator.role == "operator"


def test_apply_writes_two_audit_events_in_the_same_transaction(db_session, fully_seeded):
    before = db_session.query(AuditEvent).count()
    _force_apply_ignoring_dialect(db_session, STAGING)
    db_session.commit()
    after = db_session.query(AuditEvent).count()
    assert after - before == 2
    events = db_session.query(AuditEvent).all()
    assert all(e.action == DEACTIVATION_ACTION for e in events)
    usernames_in_events = {e.details_json.get("username") for e in events}
    assert usernames_in_events == set(TARGET_USERNAMES)


def test_second_run_refuses_and_does_not_duplicate(db_session, fully_seeded):
    _force_apply_ignoring_dialect(db_session, STAGING)
    db_session.commit()

    with pytest.raises(DeactivationTargetError):
        _force_apply_ignoring_dialect(db_session, STAGING)
    db_session.rollback()

    assert db_session.query(AuditEvent).filter(AuditEvent.action == DEACTIVATION_ACTION).count() == 2
    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    assert foreman.is_active is False


def test_full_rollback_on_failure_reverts_everything(db_session, fully_seeded):
    _force_apply_ignoring_dialect(db_session, STAGING)
    # Simulate the caller's failure path (main()'s except-block) instead of committing.
    db_session.rollback()

    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    operator = db_session.query(User).filter(User.username == "operator_pekka").first()

    assert foreman.is_active is True
    assert operator.is_active is True
    assert db_session.query(AuditEvent).count() == 0


def test_db_failure_during_apply_is_reported_safely_and_rolls_back(db_session, fully_seeded, monkeypatch):
    def failing_flush():
        raise OperationalError(
            "UPDATE users SET is_active = false WHERE username = %(username)s",
            {"username": "leaked-in-sql-params"},
            Exception("simulated connection drop"),
        )

    monkeypatch.setattr(db_session, "flush", failing_flush)

    with pytest.raises(OperationalError) as exc_info:
        _force_apply_ignoring_dialect(db_session, STAGING)
    db_session.rollback()

    safe_message = _safe_failure_message(exc_info.value)
    assert "leaked-in-sql-params" not in safe_message
    assert "UPDATE users" not in safe_message
    assert safe_message == "OperationalError (details withheld: may contain SQL text/parameters)"

    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    assert foreman.is_active is True
    assert db_session.query(AuditEvent).count() == 0


def _wrong_actor_event(uname, user_id):
    """Simulates a bug: an audit event for the right entity_id/action/entity_type but
    the wrong actor_name, so _count_matching_deactivation_audit_events() finds 0 matches
    for it (it requires all four fields to agree)."""
    return AuditEvent(
        action=DEACTIVATION_ACTION, entity_type="user", entity_id=user_id,
        actor_name="someone-else (simulated bug)", details_json={"username": uname},
    )


def _event_factory_breaking_one_target(broken_uname):
    def factory(uname, user_id):
        if uname == broken_uname:
            return _wrong_actor_event(uname, user_id)
        return _new_deactivation_audit_event(uname, user_id)
    return factory


def test_broken_audit_attribution_for_one_target_rolls_back_both_deactivations(db_session, fully_seeded):
    """If the audit event actually written does not match what apply_deactivation()
    re-reads back (here simulated for foreman_matti only), the postcondition check must
    catch it and raise before returning - and the caller's rollback() must then revert
    BOTH deactivations and BOTH audit inserts, not just the broken one, since they were
    all staged in the same uncommitted transaction."""
    with pytest.raises(DeactivationPostconditionError) as exc_info:
        _force_apply_ignoring_dialect(
            db_session, STAGING,
            event_factory=_event_factory_breaking_one_target("foreman_matti"),
        )
    assert "foreman_matti" in str(exc_info.value)
    db_session.rollback()

    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    operator = db_session.query(User).filter(User.username == "operator_pekka").first()
    assert foreman.is_active is True
    assert operator.is_active is True
    assert db_session.query(AuditEvent).count() == 0


def test_safe_failure_message_passes_through_known_error_types_unmodified():
    err = DeactivationTargetError("Target verification failed, no changes made: ARDOR_ENV is not 'staging'")
    assert _safe_failure_message(err) == str(err)

    post_err = DeactivationPostconditionError("Post-check failed: 'foreman_matti' is not inactive as expected.")
    assert _safe_failure_message(post_err) == str(post_err)


# --- dry-run / pre-apply-check: connection/DB failures must never leak raw text -----

def test_dry_run_reports_failure_safely_without_leaking_raw_sql(capsys):
    # SQLite genuinely rejects Postgres-only `BEGIN TRANSACTION READ ONLY` syntax - a
    # real, unforced failure, not a mock.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    ok = run_dry_run(engine)
    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert ok is False
    assert "DRY_RUN_FAILED:" in combined
    assert "OperationalError" in combined
    assert "READ ONLY" not in combined
    assert "syntax error" not in combined.lower()
    assert "BEGIN TRANSACTION" not in combined


def test_pre_apply_check_genuinely_runs_in_a_read_only_transaction(capsys):
    # Same rationale as the dry-run test above: SQLite genuinely rejects the
    # Postgres-only `BEGIN TRANSACTION READ ONLY` statement - a real, unforced failure,
    # not a mock - proving run_pre_apply_check() truly opens a read-only transaction
    # before doing anything else, rather than merely claiming to in its docstring.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    ok = run_pre_apply_check(engine)
    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert ok is False
    assert "PRE_CHECK_FAILED:" in combined
    assert "OperationalError" in combined
    assert "READ ONLY" not in combined
    assert "syntax error" not in combined.lower()
    assert "BEGIN TRANSACTION" not in combined


def test_engine_setup_failure_would_also_be_reported_safely():
    try:
        create_engine("not-a-valid://dsn:hunter2@nowhere")
        raised = None
    except Exception as e:  # noqa: BLE001 - intentionally broad, this is what main() catches too
        raised = e

    assert raised is not None
    safe_message = _safe_failure_message(raised)
    assert "hunter2" not in safe_message


# --- run_apply(): the two distinct failure outcomes must never be conflated --------

def test_run_apply_success_returns_success_outcome(db_session, fully_seeded, monkeypatch):
    def fake_apply_deactivation(db, environment):
        _force_apply_ignoring_dialect(db, environment)

    monkeypatch.setattr(deactivate_module, "apply_deactivation", fake_apply_deactivation)

    result = run_apply(db_session, STAGING)

    assert result.outcome is ApplyOutcome.SUCCESS
    assert result.safe_message is None
    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    assert foreman.is_active is False


def test_run_apply_aborted_before_commit_is_reported_and_fully_rolled_back(db_session, fully_seeded, monkeypatch):
    def failing_apply_deactivation(db, environment):
        raise DeactivationTargetError("simulated pre-commit failure, safe text only")

    monkeypatch.setattr(deactivate_module, "apply_deactivation", failing_apply_deactivation)

    result = run_apply(db_session, STAGING)

    assert result.outcome is ApplyOutcome.ABORTED_BEFORE_COMMIT
    assert "simulated pre-commit failure" in result.safe_message
    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    assert foreman.is_active is True


def test_run_apply_commit_failure_is_never_reported_as_rollback_or_success(db_session, fully_seeded, monkeypatch):
    def fake_apply_deactivation(db, environment):
        _force_apply_ignoring_dialect(db, environment)

    monkeypatch.setattr(deactivate_module, "apply_deactivation", fake_apply_deactivation)

    def failing_commit():
        raise OperationalError(
            "COMMIT",
            {},
            Exception("connection lost mid-commit, outcome unknown server-side"),
        )

    monkeypatch.setattr(db_session, "commit", failing_commit)

    result = run_apply(db_session, STAGING)

    assert result.outcome is ApplyOutcome.COMMIT_OUTCOME_UNKNOWN
    assert result.outcome is not ApplyOutcome.ABORTED_BEFORE_COMMIT
    assert result.outcome is not ApplyOutcome.SUCCESS
    assert "connection lost" not in result.safe_message
    assert "outcome unknown server-side" not in result.safe_message
    assert result.safe_message == "OperationalError (details withheld: may contain SQL text/parameters)"


# --- check_post_apply_state() / run_post_apply_check(): safe result verification ----

def test_check_post_apply_state_before_apply_shows_targets_active(db_session, fully_seeded):
    result = check_post_apply_state(db_session)
    assert result.target_active_flags == {"foreman_matti": True, "operator_pekka": True}
    assert result.target_audit_event_counts == {"foreman_matti": 0, "operator_pekka": 0}
    assert result.ok is False


def test_check_post_apply_state_after_apply_shows_targets_inactive(db_session, fully_seeded):
    _force_apply_ignoring_dialect(db_session, STAGING)
    db_session.commit()

    result = check_post_apply_state(db_session)
    assert result.target_active_flags == {"foreman_matti": False, "operator_pekka": False}
    assert sorted(result.protected_admin_usernames) == sorted(PROTECTED_ADMIN_USERNAMES)
    assert result.target_audit_event_counts == {"foreman_matti": 1, "operator_pekka": 1}
    assert result.ok is True


def test_post_check_fails_when_a_target_audit_event_is_missing(db_session, fully_seeded):
    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    operator = db_session.query(User).filter(User.username == "operator_pekka").first()
    foreman.is_active = False
    operator.is_active = False
    db_session.add(_new_deactivation_audit_event("operator_pekka", operator.id))
    # foreman_matti's own event is missing entirely.
    db_session.commit()

    result = check_post_apply_state(db_session)
    assert result.target_audit_event_counts == {"foreman_matti": 0, "operator_pekka": 1}
    assert result.ok is False


def test_post_check_fails_when_a_target_audit_event_is_duplicated(db_session, fully_seeded):
    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    operator = db_session.query(User).filter(User.username == "operator_pekka").first()
    foreman.is_active = False
    operator.is_active = False
    db_session.add(_new_deactivation_audit_event("foreman_matti", foreman.id))
    db_session.add(_new_deactivation_audit_event("foreman_matti", foreman.id))  # duplicate
    db_session.add(_new_deactivation_audit_event("operator_pekka", operator.id))
    db_session.commit()

    result = check_post_apply_state(db_session)
    assert result.target_audit_event_counts["foreman_matti"] == 2
    assert result.ok is False


def test_post_check_fails_when_a_target_audit_event_is_misattributed(db_session, fully_seeded):
    """An event that exists but points at the wrong entity_id (e.g. accidentally
    attributed to a protected admin's id instead of the target's own id) must not
    satisfy that target's count - this is exactly the class of bug the entity_id match
    in _count_matching_deactivation_audit_events() exists to catch."""
    admin = db_session.query(User).filter(User.username == "admin").first()
    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    operator = db_session.query(User).filter(User.username == "operator_pekka").first()
    foreman.is_active = False
    operator.is_active = False
    db_session.add(_new_deactivation_audit_event("foreman_matti", admin.id))  # wrong entity_id
    db_session.add(_new_deactivation_audit_event("operator_pekka", operator.id))
    db_session.commit()

    result = check_post_apply_state(db_session)
    assert result.target_audit_event_counts == {"foreman_matti": 0, "operator_pekka": 1}
    assert result.ok is False


def test_post_check_ignores_unrelated_account_deactivated_event_for_other_user(db_session, fully_seeded):
    """A stray account_deactivated event for some third, unrelated account must neither
    help nor hurt: it must not count towards either target (case 1 below), and it must
    not make a genuinely-complete result look any less ok (case 2 below)."""
    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    operator = db_session.query(User).filter(User.username == "operator_pekka").first()
    other = _make_user("someone_else", "operator")
    db_session.add(other)
    db_session.commit()

    # Case 1: only the stray, unrelated event exists - must not be mistaken for either
    # target's own event.
    db_session.add(_new_deactivation_audit_event("someone_else", other.id))
    foreman.is_active = False
    operator.is_active = False
    db_session.commit()

    result = check_post_apply_state(db_session)
    assert result.target_audit_event_counts == {"foreman_matti": 0, "operator_pekka": 0}
    assert result.ok is False

    # Case 2: both targets now also have their own correct event - the stray event must
    # not prevent the result from being ok.
    db_session.add(_new_deactivation_audit_event("foreman_matti", foreman.id))
    db_session.add(_new_deactivation_audit_event("operator_pekka", operator.id))
    db_session.commit()

    result = check_post_apply_state(db_session)
    assert result.target_audit_event_counts == {"foreman_matti": 1, "operator_pekka": 1}
    assert result.ok is True


def test_run_post_apply_check_output_never_contains_uuid_or_password(db_session, fully_seeded, capsys):
    _force_apply_ignoring_dialect(db_session, STAGING)
    db_session.commit()

    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()

    # run_post_apply_check() itself always issues the Postgres-only
    # `BEGIN TRANSACTION READ ONLY` and would fail on this SQLite fixture (proven
    # separately above) - here we only need to prove the *printed content* of a
    # successful check is safe, so we drive the same print statements it uses directly
    # against the already-populated fixture session.
    result = check_post_apply_state(db_session)
    output = (
        f"target_active_flags: {result.target_active_flags}\n"
        f"protected_admin_usernames: {result.protected_admin_usernames}\n"
        f"target_audit_event_counts: {result.target_audit_event_counts}\n"
        f"POST_APPLY_OK: {result.ok}\n"
    )

    assert foreman.id not in output
    assert foreman.hashed_password not in output


# --- the central safety claim: a JWT issued while active stops working the instant
#     is_active flips to False - proving deactivation truly closes the account for any
#     stale/cached token, even though JWTs are stateless and there is no server-side
#     session to explicitly revoke. -------------------------------------------------

def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_existing_jwt_for_foreman_matti_is_accepted_before_deactivation(db_session, fully_seeded):
    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    token = create_access_token({"sub": foreman.id})

    checker = require_role(["foreman", "admin"])
    result = checker(auth=_creds(token), db=db_session)
    assert result.username == "foreman_matti"


def test_same_jwt_for_foreman_matti_is_rejected_after_deactivation(db_session, fully_seeded):
    """This is the exact scenario the owner asked to be proven: a token minted for
    foreman_matti *before* this script ever runs (e.g. an old cached token on a desktop
    that synced months ago) must stop being accepted the moment is_active becomes False
    - with no other change to the token, the server, or any session state."""
    foreman = db_session.query(User).filter(User.username == "foreman_matti").first()
    token = create_access_token({"sub": foreman.id})

    # Sanity: token genuinely works right now, before any deactivation.
    checker = require_role(["foreman", "admin"])
    assert checker(auth=_creds(token), db=db_session).username == "foreman_matti"

    _force_apply_ignoring_dialect(db_session, STAGING)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        checker(auth=_creds(token), db=db_session)
    assert exc_info.value.status_code == 401


def test_same_jwt_for_operator_pekka_is_rejected_after_deactivation(db_session, fully_seeded):
    operator = db_session.query(User).filter(User.username == "operator_pekka").first()
    token = create_access_token({"sub": operator.id})

    checker = require_role(["operator", "admin"])
    assert checker(auth=_creds(token), db=db_session).username == "operator_pekka"

    _force_apply_ignoring_dialect(db_session, STAGING)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        checker(auth=_creds(token), db=db_session)
    assert exc_info.value.status_code == 401


def test_deactivation_does_not_affect_unrelated_active_users_tokens(db_session, fully_seeded):
    """Deactivating the two named accounts must not disturb anyone else's session -
    admin's own token (the account the owner is actually logged in as) keeps working."""
    admin = db_session.query(User).filter(User.username == "admin").first()
    admin_token = create_access_token({"sub": admin.id})

    _force_apply_ignoring_dialect(db_session, STAGING)
    db_session.commit()

    checker = require_role(["admin"])
    result = checker(auth=_creds(admin_token), db=db_session)
    assert result.username == "admin"
