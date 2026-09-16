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
    row with its identity unchanged, exactly one andrei.sakki row). Any exception before
    the single final commit rolls back everything - nothing is ever left partially
    applied.
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


def main() -> Optional[int]:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--apply", action="store_true",
        help="Perform the change. Default is a read-only dry-run that only reports the target check.",
    )
    args = parser.parse_args()

    try:
        engine = create_engine(settings.database_url)
    except Exception as e:
        # settings.database_url may itself contain credentials - never surface raw text.
        print(f"ENGINE_SETUP_FAILED: {_safe_failure_message(e)}", file=sys.stderr)
        return 1

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
            apply_bootstrap(db, password, settings.environment)
            db.commit()
            print("APPLY_OK: admin password reset, andrei.sakki created, 2 audit events committed.")
        except Exception as e:
            db.rollback()
            print(f"ABORTED, rolled back, nothing changed: {_safe_failure_message(e)}", file=sys.stderr)
            return 1
        finally:
            db.close()
    finally:
        password = None  # best-effort: drop the reference as soon as possible
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
