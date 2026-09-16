"""Regression guard for scripts/bootstrap_andrei_sakki_admin_reset.py.

Tests only the importable, non-interactive core (verify_target/apply_bootstrap/
_safe_failure_message). prompt_for_password() is intentionally not exercised here - it
requires a real interactive terminal by design (see its own isatty() guard) and is not
the part that needs a regression test; apply_bootstrap() takes an already-obtained
password string, which is what makes it independently testable.

Isolated by design, same pattern as the other R1/R1a/R1b regression tests: a private
in-memory SQLite session, never the process-wide engine. DATABASE_URL / STORAGE_DIR
must still be exported to isolated temporary values by the caller, because
services.api.config.Settings() is constructed at first import time, and ARDOR_ENV must
be an explicit local/dev/test value for that module-level construction to succeed (R1
made a missing ARDOR_ENV fail-closed) - the tests below pass their own `environment`
argument to verify_target()/apply_bootstrap() directly, independent of that ambient
process-level ARDOR_ENV.
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
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.auth import hash_password, verify_password
from services.api.database import Base
from services.api.models import AuditEvent, User

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.bootstrap_andrei_sakki_admin_reset import (  # noqa: E402
    ADMIN_USERNAME,
    EXPECTED_ARDOR_ENV,
    NEW_FULL_NAME,
    NEW_ROLE,
    NEW_USERNAME,
    BootstrapPostconditionError,
    BootstrapTargetError,
    apply_bootstrap,
    run_dry_run,
    run_pre_apply_check,
    verify_target,
    _safe_failure_message,
)
import scripts.bootstrap_andrei_sakki_admin_reset as bootstrap_module

ORIGINAL_ADMIN_PASSWORD = "original-admin-password-before-bootstrap"
NEW_PASSWORD = "a Unicode-safe pässwörd with spaces  "  # intentionally has trailing spaces
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


@pytest.fixture()
def seeded_admin(db_session):
    admin = User(
        username=ADMIN_USERNAME,
        full_name="System Administrator",
        role="admin",
        hashed_password=hash_password(ORIGINAL_ADMIN_PASSWORD),
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    return admin


# --- verify_target(): wrong-target cases -----------------------------------------

def test_verify_target_fails_on_sqlite_dialect(db_session, seeded_admin):
    # The isolated test engine is always SQLite - this is precisely the "wrong
    # database engine" case the real script must refuse against a real target.
    check = verify_target(db_session, STAGING)
    assert check.dialect_is_postgresql is False
    assert check.ok is False
    assert any("PostgreSQL" in p for p in check.problems)


def test_verify_target_fails_when_ardor_env_is_not_staging(db_session, seeded_admin):
    for wrong_env in ("local", "dev", "production", "", "Staging"):
        check = verify_target(db_session, wrong_env)
        assert check.ardor_env_is_staging is False
        assert check.ok is False


def test_verify_target_passes_ardor_env_check_only_for_exact_staging(db_session, seeded_admin):
    check = verify_target(db_session, "staging")
    assert check.ardor_env_is_staging is True
    # still not ok overall, because dialect is sqlite in this isolated test
    assert check.ok is False


def test_verify_target_fails_when_admin_inactive(db_session):
    admin = User(
        username=ADMIN_USERNAME, full_name="System Administrator", role="admin",
        hashed_password=hash_password(ORIGINAL_ADMIN_PASSWORD), is_active=False,
    )
    db_session.add(admin)
    db_session.commit()

    check = verify_target(db_session, STAGING)
    assert check.admin_is_active_admin_role is False
    assert check.ok is False
    assert any("inactive" in p or "role" in p for p in check.problems)


def test_verify_target_fails_when_admin_is_not_admin_role(db_session):
    admin = User(
        username=ADMIN_USERNAME, full_name="Not Really Admin", role="foreman",
        hashed_password=hash_password(ORIGINAL_ADMIN_PASSWORD), is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    check = verify_target(db_session, STAGING)
    assert check.admin_is_active_admin_role is False
    assert check.ok is False


def test_verify_target_fails_when_admin_missing(db_session):
    check = verify_target(db_session, STAGING)
    assert check.admin_is_active_admin_role is False
    assert check.ok is False


def test_verify_target_fails_when_andrei_sakki_already_exists(db_session, seeded_admin):
    db_session.add(User(
        username=NEW_USERNAME, full_name=NEW_FULL_NAME, role=NEW_ROLE,
        hashed_password=hash_password("whatever"), is_active=True,
    ))
    db_session.commit()

    check = verify_target(db_session, STAGING)
    assert check.andrei_sakki_exists is True
    assert check.ok is False


def test_verify_target_problems_never_contain_password_or_hash(db_session, seeded_admin):
    check = verify_target(db_session, "wrong-env")
    combined = " ".join(check.problems)
    assert ORIGINAL_ADMIN_PASSWORD not in combined
    assert seeded_admin.hashed_password not in combined


# --- apply_bootstrap(): refuses on bad target, no changes -----------------------

def test_apply_refuses_when_target_verification_fails_admin_inactive(db_session):
    admin = User(
        username=ADMIN_USERNAME, full_name="System Administrator", role="admin",
        hashed_password=hash_password(ORIGINAL_ADMIN_PASSWORD), is_active=False,
    )
    db_session.add(admin)
    db_session.commit()
    original_hash = admin.hashed_password

    with pytest.raises(BootstrapTargetError):
        apply_bootstrap(db_session, NEW_PASSWORD, STAGING)
    db_session.rollback()

    assert db_session.query(User).filter(User.username == NEW_USERNAME).count() == 0
    refreshed = db_session.query(User).filter(User.username == ADMIN_USERNAME).first()
    assert refreshed.hashed_password == original_hash
    assert db_session.query(AuditEvent).count() == 0


def test_apply_refuses_when_ardor_env_wrong_even_with_good_accounts(db_session, seeded_admin):
    with pytest.raises(BootstrapTargetError) as exc_info:
        apply_bootstrap(db_session, NEW_PASSWORD, "production")
    db_session.rollback()
    assert "ARDOR_ENV" in str(exc_info.value)
    assert db_session.query(User).filter(User.username == NEW_USERNAME).count() == 0


# --- apply_bootstrap(): success path (target check bypassed by using a Postgres-like
#     stand-in is not attempted here - dialect is inherently sqlite in this isolated
#     suite, so these tests exercise apply_bootstrap() via a relaxed helper that mirrors
#     production logic without the dialect gate, to keep the rest of the behaviour
#     covered without requiring a real Postgres fixture). ---------------------------

def _force_apply_ignoring_dialect(db, password, environment):
    """Test-only helper: apply_bootstrap()'s own logic, minus the dialect_is_postgresql
    gate, so the success/rollback/postcondition paths can be exercised against the
    isolated SQLite fixture. verify_target() itself is still fully tested above,
    including the dialect gate; production code always goes through the real gate."""
    from scripts.bootstrap_andrei_sakki_admin_reset import (
        verify_target as _vt,
        BOOTSTRAP_ACTOR_LABEL,
    )
    check = _vt(db, environment)
    non_dialect_problems = [p for p in check.problems if "PostgreSQL" not in p and "current_database" not in p]
    if non_dialect_problems:
        raise BootstrapTargetError("Target verification failed, no changes made: " + "; ".join(non_dialect_problems))

    admin = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    admin_id = admin.id
    admin.hashed_password = hash_password(password)

    andrei = User(
        username=NEW_USERNAME, full_name=NEW_FULL_NAME, role=NEW_ROLE,
        hashed_password=hash_password(password), is_active=True,
    )
    db.add(andrei)
    db.flush()

    db.add(AuditEvent(
        action="bootstrap_password_reset", entity_type="user", entity_id=admin_id,
        actor_name=BOOTSTRAP_ACTOR_LABEL, details_json={"username": ADMIN_USERNAME},
    ))
    db.add(AuditEvent(
        action="bootstrap_account_created", entity_type="user", entity_id=andrei.id,
        actor_name=BOOTSTRAP_ACTOR_LABEL, details_json={"username": NEW_USERNAME},
    ))
    return admin_id, andrei.id


def test_apply_creates_andrei_and_resets_admin_password(db_session, seeded_admin):
    _force_apply_ignoring_dialect(db_session, NEW_PASSWORD, STAGING)
    db_session.commit()

    admin = db_session.query(User).filter(User.username == ADMIN_USERNAME).first()
    andrei = db_session.query(User).filter(User.username == NEW_USERNAME).first()

    assert admin.role == "admin"
    assert admin.is_active is True
    assert andrei.full_name == NEW_FULL_NAME
    assert andrei.role == "admin"
    assert andrei.is_active is True


def test_apply_password_verifies_for_both_accounts_and_is_not_stripped(db_session, seeded_admin):
    _force_apply_ignoring_dialect(db_session, NEW_PASSWORD, STAGING)
    db_session.commit()

    admin = db_session.query(User).filter(User.username == ADMIN_USERNAME).first()
    andrei = db_session.query(User).filter(User.username == NEW_USERNAME).first()

    assert verify_password(NEW_PASSWORD, admin.hashed_password) is True
    assert verify_password(NEW_PASSWORD, andrei.hashed_password) is True
    assert verify_password("definitely-wrong", admin.hashed_password) is False
    assert verify_password(NEW_PASSWORD.strip(), admin.hashed_password) is False


def test_apply_uses_different_salts_for_each_account(db_session, seeded_admin):
    _force_apply_ignoring_dialect(db_session, NEW_PASSWORD, STAGING)
    db_session.commit()

    admin = db_session.query(User).filter(User.username == ADMIN_USERNAME).first()
    andrei = db_session.query(User).filter(User.username == NEW_USERNAME).first()

    assert admin.hashed_password != andrei.hashed_password
    assert admin.hashed_password.split("$", 1)[0] != andrei.hashed_password.split("$", 1)[0]


def test_apply_writes_two_audit_events_in_the_same_transaction(db_session, seeded_admin):
    before = db_session.query(AuditEvent).count()
    _force_apply_ignoring_dialect(db_session, NEW_PASSWORD, STAGING)
    db_session.commit()
    after = db_session.query(AuditEvent).count()
    assert after - before == 2
    actions = {e.action for e in db_session.query(AuditEvent).all()}
    assert "bootstrap_password_reset" in actions
    assert "bootstrap_account_created" in actions


def test_second_run_refuses_and_does_not_duplicate(db_session, seeded_admin):
    _force_apply_ignoring_dialect(db_session, NEW_PASSWORD, STAGING)
    db_session.commit()
    admin_hash_after_first_run = (
        db_session.query(User).filter(User.username == ADMIN_USERNAME).first().hashed_password
    )

    with pytest.raises(BootstrapTargetError):
        _force_apply_ignoring_dialect(db_session, "a-completely-different-password", STAGING)
    db_session.rollback()

    assert db_session.query(User).filter(User.username == NEW_USERNAME).count() == 1
    admin = db_session.query(User).filter(User.username == ADMIN_USERNAME).first()
    assert admin.hashed_password == admin_hash_after_first_run


def test_full_rollback_on_failure_reverts_everything(db_session, seeded_admin):
    original_admin_hash = seeded_admin.hashed_password
    _force_apply_ignoring_dialect(db_session, NEW_PASSWORD, STAGING)
    # Simulate the caller's failure path (main()'s except-block) instead of committing.
    db_session.rollback()

    admin = db_session.query(User).filter(User.username == ADMIN_USERNAME).first()
    andrei = db_session.query(User).filter(User.username == NEW_USERNAME).first()

    assert andrei is None
    assert admin.hashed_password == original_admin_hash
    assert db_session.query(AuditEvent).count() == 0


# --- simulated DB failure mid-apply: safe error message, full rollback ----------

def test_db_failure_during_apply_is_reported_safely_and_rolls_back(db_session, seeded_admin, monkeypatch):
    def failing_flush():
        raise OperationalError(
            "INSERT INTO users (username, hashed_password) VALUES (%(username)s, %(hashed_password)s)",
            {"username": "leaked-in-sql-params", "hashed_password": "should-never-be-printed"},
            Exception("simulated connection drop"),
        )

    monkeypatch.setattr(db_session, "flush", failing_flush)

    with pytest.raises(OperationalError) as exc_info:
        _force_apply_ignoring_dialect(db_session, NEW_PASSWORD, STAGING)
    db_session.rollback()

    safe_message = _safe_failure_message(exc_info.value)
    assert "should-never-be-printed" not in safe_message
    assert "leaked-in-sql-params" not in safe_message
    assert "INSERT INTO" not in safe_message
    assert safe_message == "OperationalError (details withheld: may contain SQL text/parameters)"

    assert db_session.query(User).filter(User.username == NEW_USERNAME).count() == 0
    admin = db_session.query(User).filter(User.username == ADMIN_USERNAME).first()
    assert admin.hashed_password == seeded_admin.hashed_password
    assert db_session.query(AuditEvent).count() == 0


def test_safe_failure_message_passes_through_known_error_types_unmodified():
    err = BootstrapTargetError("Target verification failed, no changes made: ARDOR_ENV is not 'staging'")
    assert _safe_failure_message(err) == str(err)

    post_err = BootstrapPostconditionError("Post-check failed: expected exactly 1 'andrei.sakki' row, found 2.")
    assert _safe_failure_message(post_err) == str(post_err)


# --- dry-run / pre-apply-check: connection/DB failures must never leak raw text -----

def test_dry_run_reports_failure_safely_without_leaking_raw_sql(capsys):
    # SQLite genuinely rejects Postgres-only `BEGIN TRANSACTION READ ONLY` syntax - a
    # real, unforced failure, not a mock - giving a realistic exception whose raw text
    # contains the failing statement.
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


def test_pre_apply_check_reports_failure_safely_without_leaking_raw_text(monkeypatch, capsys):
    def fake_verify_target(db, environment):
        raise RuntimeError(
            "connection string was postgresql://real_user:super-secret-password@host/db"
        )

    monkeypatch.setattr(bootstrap_module, "verify_target", fake_verify_target)

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    ok = run_pre_apply_check(engine)
    captured = capsys.readouterr()
    combined = captured.out + captured.err

    assert ok is False
    assert "PRE_CHECK_FAILED:" in combined
    assert "RuntimeError" in combined
    assert "super-secret-password" not in combined
    assert "real_user" not in combined


def test_engine_setup_failure_would_also_be_reported_safely():
    # main() wraps create_engine() itself the same way, since a malformed
    # settings.database_url can embed a password in the raw connection string; the
    # wrapping logic is identical to the one already proven above, exercised directly
    # here against a deliberately invalid DSN containing an obvious "secret".
    try:
        create_engine("not-a-valid://dsn:hunter2@nowhere")
        raised = None
    except Exception as e:  # noqa: BLE001 - intentionally broad, this is what main() catches too
        raised = e

    assert raised is not None
    safe_message = _safe_failure_message(raised)
    assert "hunter2" not in safe_message
