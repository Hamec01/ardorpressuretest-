#!/usr/bin/env python3
"""One-time, explicitly-authorized bootstrap/reset for exactly two accounts
(ADR-005 SS13 legacy-migration prerequisite / R1 "controlled bootstrap" requirement).

Targets, nothing else:
  1. Create a new account: username=andrei.sakki, full_name="Andrei Sakki", role=admin.
  2. Reset the password hash of the EXISTING username=admin account. Its role,
     is_active, username and every other field are left untouched.

Safety model:
  - The password is captured exactly once, interactively, via getpass - never from
    argv, an environment variable, a file, or piped/non-interactive stdin. It is
    accepted byte-for-byte: any characters, Unicode, leading/trailing spaces are never
    stripped or otherwise normalized.
  - The same entered password is hashed independently for each account. hash_password()
    generates a fresh random salt on every call, so the two stored hashes always differ
    from each other even though the plaintext is identical - this is intentional for
    this narrow bootstrap operation, not a general multi-account password policy.
  - Default mode is a read-only dry-run: opens the target database in an explicit
    `BEGIN TRANSACTION READ ONLY` transaction, runs the full target verification below,
    and always ends in ROLLBACK. No password prompt occurs in this mode.
  - --apply verifies the target TWICE: once before the password prompt (so a wrong
    target is rejected before anyone is asked to type a password at all), and once more
    as the first thing inside the write transaction, before any row is touched. A
    lightweight postcondition check runs again immediately before commit - it does not
    repeat the precondition (which would now trivially disagree with itself, since the
    operation's own uncommitted change is what makes andrei.sakki exist); instead it
    confirms the operation produced exactly the expected end state (exactly one admin
    row with its identity unchanged, exactly one andrei.sakki row).
  - Two distinct failure outcomes are never conflated:
      * ABORTED_BEFORE_COMMIT - the exception happened before db.commit() was ever
        called (target verification, or any error while staging the changes). Rollback
        is guaranteed to fully revert the session, and it is safe to report "nothing
        changed".
      * COMMIT_OUTCOME_UNKNOWN - the exception happened during/around db.commit() itself
        (e.g. the connection drops after the server processes the commit but before the
        client receives acknowledgement). Calling rollback() here would be misleading:
        you cannot roll back a commit that may have already happened, and there is no
        way to know from the client side whether it did. This case is never reported as
        "rolled back" or "nothing changed" - the operator is told to stop and check the
        database read-only (--post-check) before deciding on next steps, and never to
        blindly re-run --apply.
    The success message is printed strictly after both of these steps have completed
    without error - never from inside the block that is allowed to call rollback().
  - --post-check (read-only, independent of --apply) verifies the *result* of a
    completed or ambiguous apply: exactly two active users with role=admin, and exactly
    the two expected bootstrap audit events - never printing a password, hash, or UUID.
  - Target verification, required to pass in every case above:
      * ARDOR_ENV is exactly "staging" (not local/dev/test, not anything else)
      * the database dialect is PostgreSQL (never SQLite)
      * current_database() is exactly "ardor_pressure_test" - deliberately not tied to
        any container IP address, which is not stable across restarts/rebuilds
      * the existing "admin" user is_active and has role == "admin"
      * no user has username == "andrei.sakki" yet
    Any failing condition aborts with no changes. The andrei.sakki-absence condition is
    also what makes a second run safe: once it exists, verification refuses to run again.
  - Never touches any other user row, role, log, or the foreman_matti legacy-attribution
    references described in ADR-005 SS13 - that reassignment is a separate, later step
    that requires andrei.sakki's real user_id to already exist.
  - Never prints a password, a password hash, a user UUID, or the text/parameters of any
    SQL statement. Unexpected exceptions (anything other than this script's own
    controlled error types) are reported only by exception class name, since driver-level
    exceptions (SQLAlchemy/psycopg2) often embed the failing statement and bound values
    in their string representation - and a malformed settings.database_url itself may
    embed a password. This applies uniformly to the dry-run, the pre-apply check, and
    the write transaction: none of the three ever surfaces a raw exception's text.
"""
import argparse
import getpass
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from services.api.auth import hash_password
from services.api.config import settings
from services.api.models import AuditEvent, User

ADMIN_USERNAME = "admin"
NEW_USERNAME = "andrei.sakki"
NEW_FULL_NAME = "Andrei Sakki"
NEW_ROLE = "admin"
EXPECTED_ARDOR_ENV = "staging"
EXPECTED_DATABASE_NAME = "ardor_pressure_test"
BOOTSTRAP_ACTOR_LABEL = "bootstrap_script (owner-authorized, out-of-band)"
MIN_PASSWORD_LENGTH = 6  # matches the already-approved policy (PRODUCT_REQUIREMENTS.md SS6.2), not a new rule


class BootstrapTargetError(RuntimeError):
    """Raised when the target database/environment/accounts do not match what this
    script is allowed to touch. Message text is always safe to print."""


class BootstrapPostconditionError(RuntimeError):
    """Raised if the operation's own result does not look exactly as expected,
    immediately before commit. Message text is always safe to print."""


@dataclass
class TargetCheckResult:
    ardor_env_is_staging: bool
    dialect_is_postgresql: bool
    current_database_name: Optional[str]
    current_database_is_expected: bool
    admin_is_active_admin_role: bool
    andrei_sakki_exists: bool
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def verify_target(db: Session, environment: str) -> TargetCheckResult:
    """Runs every target check described in the module docstring. Safe to call inside
    a read-only transaction (only issues SELECTs) or at the start of a write
    transaction (before any mutation)."""
    engine = db.get_bind()
    dialect_is_postgresql = engine.dialect.name == "postgresql"

    current_database_name = None
    current_database_is_expected = False
    if dialect_is_postgresql:
        current_database_name = db.execute(text("SELECT current_database();")).scalar()
        current_database_is_expected = current_database_name == EXPECTED_DATABASE_NAME

    ardor_env_is_staging = environment.strip() == EXPECTED_ARDOR_ENV

    admin_rows = db.query(User).filter(User.username == ADMIN_USERNAME).all()
    admin_is_active_admin_role = (
        len(admin_rows) == 1 and admin_rows[0].is_active and admin_rows[0].role == "admin"
    )

    andrei_sakki_exists = db.query(User).filter(User.username == NEW_USERNAME).count() > 0

    problems: List[str] = []
    if not ardor_env_is_staging:
        problems.append(f"ARDOR_ENV is not '{EXPECTED_ARDOR_ENV}'")
    if not dialect_is_postgresql:
        problems.append("database dialect is not PostgreSQL")
    elif not current_database_is_expected:
        problems.append(f"current_database() is not '{EXPECTED_DATABASE_NAME}'")
    if not admin_is_active_admin_role:
        problems.append(f"'{ADMIN_USERNAME}' is missing, inactive, or not role='admin'")
    if andrei_sakki_exists:
        problems.append(f"'{NEW_USERNAME}' already exists")

    return TargetCheckResult(
        ardor_env_is_staging=ardor_env_is_staging,
        dialect_is_postgresql=dialect_is_postgresql,
        current_database_name=current_database_name,
        current_database_is_expected=current_database_is_expected,
        admin_is_active_admin_role=admin_is_active_admin_role,
        andrei_sakki_exists=andrei_sakki_exists,
        problems=problems,
    )


@dataclass
class ApplyResult:
    admin_password_changed: bool
    andrei_created: bool


def apply_bootstrap(db: Session, password: str, environment: str) -> ApplyResult:
    """Performs both account changes and two audit events on the given session.

    Does NOT call db.commit() or db.rollback() - that is the caller's responsibility,
    so a single external transaction boundary covers everything this function does.
    Raises BootstrapTargetError (nothing written) if target verification fails, or
    BootstrapPostconditionError (still nothing committed - caller must roll back) if the
    result immediately before return does not look exactly as expected.
    """
    check = verify_target(db, environment)
    if not check.ok:
        raise BootstrapTargetError(
            "Target verification failed, no changes made: " + "; ".join(check.problems)
        )

    admin = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    admin_id = admin.id
    admin.hashed_password = hash_password(password)

    andrei = User(
        username=NEW_USERNAME,
        full_name=NEW_FULL_NAME,
        role=NEW_ROLE,
        hashed_password=hash_password(password),
        is_active=True,
    )
    db.add(andrei)
    db.flush()  # assign andrei.id without committing, for the audit entity_id below

    db.add(AuditEvent(
        action="bootstrap_password_reset",
        entity_type="user",
        entity_id=admin_id,
        actor_name=BOOTSTRAP_ACTOR_LABEL,
        details_json={"username": ADMIN_USERNAME, "reason": "R1 bootstrap: replace known seed password"},
    ))
    db.add(AuditEvent(
        action="bootstrap_account_created",
        entity_type="user",
        entity_id=andrei.id,
        actor_name=BOOTSTRAP_ACTOR_LABEL,
        details_json={"username": NEW_USERNAME, "role": NEW_ROLE, "reason": "ADR-005 legacy-migration target account"},
    ))

    # Postcondition check, immediately before returning to the caller for commit: not a
    # repeat of the precondition (which would now trivially read andrei_sakki_exists as
    # True, since we just added it) - this instead confirms the operation itself
    # produced exactly the expected shape, closing the window against anything else
    # having concurrently written a conflicting row in the same uncommitted transaction.
    andrei_rows = db.query(User).filter(User.username == NEW_USERNAME).all()
    if len(andrei_rows) != 1:
        raise BootstrapPostconditionError(
            f"Post-check failed: expected exactly 1 '{NEW_USERNAME}' row, found {len(andrei_rows)}."
        )
    admin_rows = db.query(User).filter(User.username == ADMIN_USERNAME).all()
    if len(admin_rows) != 1 or admin_rows[0].id != admin_id:
        raise BootstrapPostconditionError(
            f"Post-check failed: '{ADMIN_USERNAME}' row identity changed unexpectedly."
        )

    return ApplyResult(admin_password_changed=True, andrei_created=True)


class ApplyOutcome(Enum):
    SUCCESS = "success"
    ABORTED_BEFORE_COMMIT = "aborted_before_commit"
    COMMIT_OUTCOME_UNKNOWN = "commit_outcome_unknown"


@dataclass
class ApplyRunResult:
    outcome: ApplyOutcome
    safe_message: Optional[str] = None


def run_apply(db: Session, password: str, environment: str) -> ApplyRunResult:
    """Runs apply_bootstrap() and db.commit() as two separately-handled steps, so a
    failure while staging the changes and a failure during commit are never conflated:

    - A failure from apply_bootstrap() happens strictly before commit is ever called;
      db.rollback() is guaranteed to fully revert it, so this is ABORTED_BEFORE_COMMIT.
    - A failure from db.commit() itself gets no rollback call at all: the commit may
      have already reached the server, so "rolled back, nothing changed" would be a
      false claim. This is COMMIT_OUTCOME_UNKNOWN - the caller must not treat it as
      either success or a safe no-op, and must not blindly retry.

    Never raises: every outcome, including an unexpected exception, comes back as a
    ApplyRunResult with an already-sanitized safe_message.
    """
    try:
        apply_bootstrap(db, password, environment)
    except Exception as e:
        db.rollback()
        return ApplyRunResult(ApplyOutcome.ABORTED_BEFORE_COMMIT, _safe_failure_message(e))

    try:
        db.commit()
    except Exception as e:
        return ApplyRunResult(ApplyOutcome.COMMIT_OUTCOME_UNKNOWN, _safe_failure_message(e))

    return ApplyRunResult(ApplyOutcome.SUCCESS)


def _safe_failure_message(exc: BaseException) -> str:
    """Never surface a raw exception's full text for anything outside this script's own
    controlled error types - SQLAlchemy/psycopg2 exceptions often embed the failing SQL
    statement and its bound parameters (which may include a password hash) in str(exc)."""
    if isinstance(exc, (BootstrapTargetError, BootstrapPostconditionError)):
        return str(exc)
    return f"{type(exc).__name__} (details withheld: may contain SQL text/parameters)"


def prompt_for_password() -> str:
    if not sys.stdin.isatty():
        raise RuntimeError(
            "Refusing to proceed: no interactive terminal detected. The password must "
            "be typed directly by the owner; it is never accepted from argv, an "
            "environment variable, a file, or piped/non-interactive input."
        )
    first = getpass.getpass(
        f"Enter the new password for BOTH '{ADMIN_USERNAME}' and '{NEW_USERNAME}' (input hidden): "
    )
    second = getpass.getpass("Re-enter the same password to confirm: ")
    if first != second:
        raise RuntimeError("Passwords did not match - aborting, nothing changed.")
    if len(first) < MIN_PASSWORD_LENGTH:
        raise RuntimeError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters - aborting, nothing changed.")
    return first


def _print_target_check(check: TargetCheckResult) -> None:
    print(f"ARDOR_ENV_is_staging: {check.ardor_env_is_staging}")
    print(f"dialect_is_postgresql: {check.dialect_is_postgresql}")
    print(f"current_database: {check.current_database_name}")
    print(f"current_database_is_expected: {check.current_database_is_expected}")
    print(f"admin_is_active_admin_role: {check.admin_is_active_admin_role}")
    print(f"andrei_sakki_exists: {check.andrei_sakki_exists}")
    print(f"TARGET_OK: {check.ok}")
    if not check.ok:
        print("problems: " + "; ".join(check.problems))


def run_dry_run(engine) -> bool:
    """Read-only guard against the target database. Returns True iff the target check
    passes. Never writes, always rolls back its own transaction. Any failure (connection
    error, unexpected DB error, etc.) is reported via a safe message only - never the
    raw exception text, which for driver-level errors (and for a malformed
    settings.database_url itself) can embed a connection string, SQL text, or bound
    parameters."""
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        db.execute(text("BEGIN TRANSACTION READ ONLY;"))
        ro = db.execute(text("SHOW transaction_read_only;")).scalar()
        print(f"transaction_read_only: {ro}")
        if ro != "on":
            print("STOP: transaction_read_only is not 'on' - aborting before target checks.")
            return False
        check = verify_target(db, settings.environment)
        _print_target_check(check)
        return check.ok
    except Exception as e:
        print(f"DRY_RUN_FAILED: {_safe_failure_message(e)}", file=sys.stderr)
        return False
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()


def run_pre_apply_check(engine) -> bool:
    """Target verification run before the password prompt, in its own read-write
    session (no explicit READ ONLY wrapper needed here - it issues no writes either
    way). Never writes. Any failure is reported via a safe message only, same rationale
    as run_dry_run()."""
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        check = verify_target(db, settings.environment)
        _print_target_check(check)
        return check.ok
    except Exception as e:
        print(f"PRE_CHECK_FAILED: {_safe_failure_message(e)}", file=sys.stderr)
        return False
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()


EXPECTED_ACTIVE_ADMIN_COUNT = 2
BOOTSTRAP_AUDIT_ACTIONS = ("bootstrap_password_reset", "bootstrap_account_created")


@dataclass
class PostApplyCheckResult:
    active_admin_usernames: List[str]
    bootstrap_audit_event_count: int

    @property
    def ok(self) -> bool:
        return (
            len(self.active_admin_usernames) == EXPECTED_ACTIVE_ADMIN_COUNT
            and self.bootstrap_audit_event_count == len(BOOTSTRAP_AUDIT_ACTIONS)
        )


def check_post_apply_state(db: Session) -> PostApplyCheckResult:
    """Pure query logic for the post-apply result, factored out of run_post_apply_check()
    so it is directly testable without needing the PostgreSQL-only `BEGIN TRANSACTION
    READ ONLY` statement that the CLI-facing wrapper adds. Only usernames and audit
    action names are read - never ids, hashes, or passwords."""
    active_admins = (
        db.query(User.username)
        .filter(User.role == "admin", User.is_active == True)  # noqa: E712
        .order_by(User.username)
        .all()
    )
    audit_count = (
        db.query(AuditEvent)
        .filter(AuditEvent.action.in_(BOOTSTRAP_AUDIT_ACTIONS))
        .count()
    )
    return PostApplyCheckResult(
        active_admin_usernames=[u.username for u in active_admins],
        bootstrap_audit_event_count=audit_count,
    )


def run_post_apply_check(engine) -> bool:
    """Read-only verification of the *result* of a completed (or ambiguous, see
    COMMIT_OUTCOME_UNKNOWN) apply. Never writes, always rolls back. Any failure is
    reported via a safe message only, same rationale as run_dry_run()."""
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        db.execute(text("BEGIN TRANSACTION READ ONLY;"))
        ro = db.execute(text("SHOW transaction_read_only;")).scalar()
        print(f"transaction_read_only: {ro}")
        if ro != "on":
            print("STOP: transaction_read_only is not 'on' - aborting before checks.")
            return False

        result = check_post_apply_state(db)
        print(f"active_admin_count: {len(result.active_admin_usernames)} (expected {EXPECTED_ACTIVE_ADMIN_COUNT})")
        print(f"active_admin_usernames: {result.active_admin_usernames}")
        print(
            f"bootstrap_audit_event_count: {result.bootstrap_audit_event_count} "
            f"(expected {len(BOOTSTRAP_AUDIT_ACTIONS)})"
        )
        print(f"POST_APPLY_OK: {result.ok}")
        return result.ok
    except Exception as e:
        print(f"POST_APPLY_CHECK_FAILED: {_safe_failure_message(e)}", file=sys.stderr)
        return False
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()


def main() -> Optional[int]:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply", action="store_true",
        help="Perform the change. Default is a read-only dry-run that only reports the target check.",
    )
    mode.add_argument(
        "--post-check", action="store_true",
        help="Read-only: verify two active admin-role users and the two bootstrap audit "
             "events exist. Does not apply anything.",
    )
    args = parser.parse_args()

    try:
        engine = create_engine(settings.database_url)
    except Exception as e:
        # settings.database_url may itself contain credentials - never surface raw text.
        print(f"ENGINE_SETUP_FAILED: {_safe_failure_message(e)}", file=sys.stderr)
        return 1

    if args.post_check:
        ok = run_post_apply_check(engine)
        return 0 if ok else 1

    if not args.apply:
        ok = run_dry_run(engine)
        return 0 if ok else 1

    # --apply path: verify the target BEFORE prompting for a password at all.
    if not run_pre_apply_check(engine):
        print("REFUSING: target verification failed - no password will be requested.", file=sys.stderr)
        return 1

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    password = None
    try:
        password = prompt_for_password()
        db = SessionLocal()
        try:
            result = run_apply(db, password, settings.environment)
        finally:
            db.close()
    finally:
        password = None  # best-effort: drop the reference as soon as possible

    if result.outcome is ApplyOutcome.ABORTED_BEFORE_COMMIT:
        print(f"ABORTED BEFORE COMMIT, rolled back, nothing changed: {result.safe_message}", file=sys.stderr)
        return 1

    if result.outcome is ApplyOutcome.COMMIT_OUTCOME_UNKNOWN:
        print(f"COMMIT OUTCOME UNKNOWN: {result.safe_message}", file=sys.stderr)
        print(
            "Do not re-run --apply. The commit may have already reached the server even "
            "though this client did not receive confirmation. Run this script with "
            "--post-check (read-only) to determine the actual state before deciding on "
            "next steps.",
            file=sys.stderr,
        )
        return 2

    # Only reached on ApplyOutcome.SUCCESS - outside the block that is allowed to call
    # rollback(), and after commit() has already returned without raising.
    print("APPLY_OK: admin password reset, andrei.sakki created, 2 audit events committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
