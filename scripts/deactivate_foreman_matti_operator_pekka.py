#!/usr/bin/env python3
"""One-time, explicitly-authorized deactivation of exactly two legacy seed accounts
(R1c - narrow follow-up to the andrei.sakki bootstrap, ADR-005 SS13 lineage).

Targets, nothing else:
  1. username=foreman_matti - set is_active=False. Nothing else on the row changes.
  2. username=operator_pekka - set is_active=False. Nothing else on the row changes.

Why this is safe (confirmed read-only, before this script was written):
  - Every column across the schema that stores a user's id as a foreign reference
    (audit_events.user_id, planned_test_lists.created_by_user_id,
    pressure_test_records.confirmed_by_user_id, pressure_tests.pipecloud_updated_by_user_id)
    is a plain character-varying column with NO foreign-key constraint to users.id -
    confirmed via information_schema.table_constraints. Flipping is_active can therefore
    never cascade-delete or reassign any referencing row: those references are just text
    that stays exactly as it is regardless of the referenced user's active state.
  - foreman_matti has 132 such references (95 audit_events, 7 planned_test_lists,
    1 pressure_test_records, 29 pressure_tests); operator_pekka has 0 references anywhere.
    These are row counts only - they do not by themselves prove who or what produced that
    activity, or that either account is currently unused. The owner has separately
    confirmed that, as of this script's authorization, nobody currently logs in as either
    account and neither is used for desktop-app sync.
  - JWTs are stateless and re-checked against is_active on every request (see
    require_role() in services/api/auth.py / services/api/routes/*), so a stale token for
    either account starts failing with 401 as soon as this change is applied - it is not
    "logged out" from a session that exists server-side, because no such session exists.
  - This script never deletes or reassigns rows, never touches roles, never touches any
    account other than the two named above, and never touches admin or andrei.sakki
    except to verify (never modify) that both remain active admin throughout.

Safety model (mirrors scripts/bootstrap_andrei_sakki_admin_reset.py):
  - Default mode is a read-only dry-run: opens the target database in an explicit
    `BEGIN TRANSACTION READ ONLY` transaction, runs the full target verification below,
    and always ends in ROLLBACK.
  - --apply verifies the target TWICE: once before touching anything (inside its own
    explicit read-only transaction), and once more as the first thing inside the write
    transaction. A postcondition check runs again immediately before commit, confirming
    the operation produced exactly the expected end state: both targets inactive, both
    protected accounts still active admin, and exactly one correctly-attributed
    deactivation audit event (matching action, entity_type, entity_id, actor_name) per
    target - it does not just repeat the precondition.
  - Two distinct failure outcomes are never conflated:
      * ABORTED_BEFORE_COMMIT - the exception happened before db.commit() was ever
        called. db.rollback() is guaranteed to fully revert the session; safe to report
        "nothing changed".
      * COMMIT_OUTCOME_UNKNOWN - the exception happened during/around db.commit() itself.
        Never rolled back, never reported as "nothing changed" - the operator is told to
        stop and check the database read-only (--post-check), and never to blindly
        re-run --apply.
    The success message is printed strictly after both steps complete without error -
    never from inside the block that is allowed to call rollback().
  - --post-check (read-only, independent of --apply) verifies the *result*: both targets
    inactive, admin and andrei.sakki both still active admin, and exactly one
    correctly-attributed deactivation audit event per target (matched by entity_id to
    that specific user, not just a global count of the action name - an unrelated
    account_deactivated event for some other user must never count towards either
    target) - never printing a password, hash, or UUID.
  - Target verification, required to pass in every case above:
      * ARDOR_ENV is exactly "staging"
      * the database dialect is PostgreSQL (never SQLite)
      * current_database() is exactly "ardor_pressure_test" - never tied to a container IP
      * admin AND andrei.sakki are both currently active with role == "admin"
      * foreman_matti AND operator_pekka are both currently active (this is also the
        idempotency guard: once either is already inactive, verification refuses to run
        again rather than silently no-op'ing or double-writing audit events)
  - No password or other secret is involved in this operation, so there is no
    interactive prompt; --apply still requires the target checks above to pass first.
  - Never prints a password, a password hash, a user UUID, or the text/parameters of any
    SQL statement. Unexpected exceptions (anything other than this script's own
    controlled error types) are reported only by exception class name.
"""
import argparse
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from services.api.config import settings
from services.api.models import AuditEvent, User

PROTECTED_ADMIN_USERNAMES = ("admin", "andrei.sakki")
TARGET_USERNAMES = ("foreman_matti", "operator_pekka")
EXPECTED_ARDOR_ENV = "staging"
EXPECTED_DATABASE_NAME = "ardor_pressure_test"
DEACTIVATION_ACTOR_LABEL = "r1c_deactivation_script (owner-authorized, out-of-band)"
DEACTIVATION_ACTION = "account_deactivated"


class DeactivationTargetError(RuntimeError):
    """Raised when the target database/environment/accounts do not match what this
    script is allowed to touch. Message text is always safe to print."""


class DeactivationPostconditionError(RuntimeError):
    """Raised if the operation's own result does not look exactly as expected,
    immediately before commit. Message text is always safe to print."""


@dataclass
class TargetCheckResult:
    ardor_env_is_staging: bool
    dialect_is_postgresql: bool
    current_database_name: Optional[str]
    current_database_is_expected: bool
    protected_admins_ok: bool
    targets_currently_active: bool
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

    protected_admins_ok = True
    for uname in PROTECTED_ADMIN_USERNAMES:
        rows = db.query(User).filter(User.username == uname).all()
        if not (len(rows) == 1 and rows[0].is_active and rows[0].role == "admin"):
            protected_admins_ok = False

    targets_currently_active = True
    for uname in TARGET_USERNAMES:
        rows = db.query(User).filter(User.username == uname).all()
        if not (len(rows) == 1 and rows[0].is_active):
            targets_currently_active = False

    problems: List[str] = []
    if not ardor_env_is_staging:
        problems.append(f"ARDOR_ENV is not '{EXPECTED_ARDOR_ENV}'")
    if not dialect_is_postgresql:
        problems.append("database dialect is not PostgreSQL")
    elif not current_database_is_expected:
        problems.append(f"current_database() is not '{EXPECTED_DATABASE_NAME}'")
    if not protected_admins_ok:
        problems.append(
            "one or both protected accounts (admin, andrei.sakki) are missing, "
            "inactive, or not role='admin'"
        )
    if not targets_currently_active:
        problems.append(
            "one or both target accounts (foreman_matti, operator_pekka) are missing "
            "or already inactive - refusing to re-run"
        )

    return TargetCheckResult(
        ardor_env_is_staging=ardor_env_is_staging,
        dialect_is_postgresql=dialect_is_postgresql,
        current_database_name=current_database_name,
        current_database_is_expected=current_database_is_expected,
        protected_admins_ok=protected_admins_ok,
        targets_currently_active=targets_currently_active,
        problems=problems,
    )


@dataclass
class ApplyResult:
    deactivated_usernames: List[str]


def _new_deactivation_audit_event(uname: str, user_id: str) -> AuditEvent:
    return AuditEvent(
        action=DEACTIVATION_ACTION,
        entity_type="user",
        entity_id=user_id,
        actor_name=DEACTIVATION_ACTOR_LABEL,
        details_json={
            "username": uname,
            "reason": "R1c: owner confirmed this account is not currently used for login or desktop sync",
        },
    )


def _count_matching_deactivation_audit_events(db: Session, user_id: str) -> int:
    """Counts audit events correctly attributed to exactly this user id - matched on
    entity_id, action, entity_type, AND actor_name, never just the action name alone.
    An account_deactivated event belonging to some other user must never be counted
    here."""
    return (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_id == user_id,
            AuditEvent.action == DEACTIVATION_ACTION,
            AuditEvent.entity_type == "user",
            AuditEvent.actor_name == DEACTIVATION_ACTOR_LABEL,
        )
        .count()
    )


def apply_deactivation(db: Session, environment: str) -> ApplyResult:
    """Performs both account changes and two audit events on the given session.

    Does NOT call db.commit() or db.rollback() - that is the caller's responsibility,
    so a single external transaction boundary covers everything this function does.
    Raises DeactivationTargetError (nothing written) if target verification fails, or
    DeactivationPostconditionError (still nothing committed - caller must roll back) if
    the result immediately before return does not look exactly as expected. Because both
    deactivations and both audit events are staged on the same session inside this one
    function, a postcondition failure at any point below means the caller's rollback()
    reverts everything staged here, not just the part that failed.
    """
    check = verify_target(db, environment)
    if not check.ok:
        raise DeactivationTargetError(
            "Target verification failed, no changes made: " + "; ".join(check.problems)
        )

    protected_ids_before = {
        uname: db.query(User).filter(User.username == uname).first().id
        for uname in PROTECTED_ADMIN_USERNAMES
    }

    target_user_ids: Dict[str, str] = {}
    for uname in TARGET_USERNAMES:
        user = db.query(User).filter(User.username == uname).first()
        user.is_active = False
        target_user_ids[uname] = user.id
        db.add(_new_deactivation_audit_event(uname, user.id))

    db.flush()  # stage the two UPDATEs and two INSERTs now, so a constraint violation
    # surfaces here (still safely rollback-able by the caller) instead of silently
    # waiting until commit.

    # Postcondition check, immediately before returning to the caller for commit: not a
    # repeat of the precondition (which would now trivially disagree with itself) -
    # confirms the operation produced exactly the expected end state.
    for uname in TARGET_USERNAMES:
        row = db.query(User).filter(User.username == uname).first()
        if row is None or row.is_active is not False:
            raise DeactivationPostconditionError(
                f"Post-check failed: '{uname}' is not inactive as expected."
            )
    for uname in PROTECTED_ADMIN_USERNAMES:
        row = db.query(User).filter(User.username == uname).first()
        if row is None or row.id != protected_ids_before[uname] or not row.is_active or row.role != "admin":
            raise DeactivationPostconditionError(
                f"Post-check failed: protected account '{uname}' changed unexpectedly."
            )

    # Postcondition check on the audit trail itself: exactly one event correctly
    # attributed to each target's own id - not a repeat of "was an INSERT issued", but a
    # genuine re-read confirming what actually landed matches what was intended.
    for uname in TARGET_USERNAMES:
        matching_count = _count_matching_deactivation_audit_events(db, target_user_ids[uname])
        if matching_count != 1:
            raise DeactivationPostconditionError(
                f"Post-check failed: expected exactly 1 deactivation audit event for "
                f"'{uname}', found {matching_count}."
            )

    return ApplyResult(deactivated_usernames=list(target_user_ids.keys()))


class ApplyOutcome(Enum):
    SUCCESS = "success"
    ABORTED_BEFORE_COMMIT = "aborted_before_commit"
    COMMIT_OUTCOME_UNKNOWN = "commit_outcome_unknown"


@dataclass
class ApplyRunResult:
    outcome: ApplyOutcome
    safe_message: Optional[str] = None


def run_apply(db: Session, environment: str) -> ApplyRunResult:
    """Runs apply_deactivation() and db.commit() as two separately-handled steps, so a
    failure while staging the changes and a failure during commit are never conflated -
    see module docstring for the ABORTED_BEFORE_COMMIT / COMMIT_OUTCOME_UNKNOWN
    distinction. Never raises: every outcome comes back as an ApplyRunResult with an
    already-sanitized safe_message."""
    try:
        apply_deactivation(db, environment)
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
    statement and its bound parameters in str(exc)."""
    if isinstance(exc, (DeactivationTargetError, DeactivationPostconditionError)):
        return str(exc)
    return f"{type(exc).__name__} (details withheld: may contain SQL text/parameters)"


def _print_target_check(check: TargetCheckResult) -> None:
    print(f"ARDOR_ENV_is_staging: {check.ardor_env_is_staging}")
    print(f"dialect_is_postgresql: {check.dialect_is_postgresql}")
    print(f"current_database: {check.current_database_name}")
    print(f"current_database_is_expected: {check.current_database_is_expected}")
    print(f"protected_admins_ok: {check.protected_admins_ok}")
    print(f"targets_currently_active: {check.targets_currently_active}")
    print(f"TARGET_OK: {check.ok}")
    if not check.ok:
        print("problems: " + "; ".join(check.problems))


def run_dry_run(engine) -> bool:
    """Read-only guard against the target database. Returns True iff the target check
    passes. Never writes, always rolls back its own transaction."""
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
    """Target verification run before any write, explicitly inside its own read-only
    transaction (same discipline as run_dry_run()), on a session distinct from the one
    --apply later uses to write. verify_target() itself only issues SELECTs, but wrapping
    it in an explicit `BEGIN TRANSACTION READ ONLY` here guarantees that, not merely
    assumes it. Never writes, always rolls back. Any failure is reported via a safe
    message only, same rationale as run_dry_run()."""
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
        print(f"PRE_CHECK_FAILED: {_safe_failure_message(e)}", file=sys.stderr)
        return False
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()


@dataclass
class PostApplyCheckResult:
    target_active_flags: dict
    protected_admin_usernames: List[str]
    target_audit_event_counts: Dict[str, int]

    @property
    def ok(self) -> bool:
        return (
            all(v is False for v in self.target_active_flags.values())
            and len(self.target_active_flags) == len(TARGET_USERNAMES)
            and sorted(self.protected_admin_usernames) == sorted(PROTECTED_ADMIN_USERNAMES)
            and len(self.target_audit_event_counts) == len(TARGET_USERNAMES)
            and all(c == 1 for c in self.target_audit_event_counts.values())
        )


def check_post_apply_state(db: Session) -> PostApplyCheckResult:
    """Pure query logic for the post-apply result, factored out of run_post_apply_check()
    so it is directly testable without needing the PostgreSQL-only `BEGIN TRANSACTION
    READ ONLY` statement that the CLI-facing wrapper adds. Only usernames and event
    counts are read - never ids, hashes, or passwords.

    The audit check is per-target, matched by entity_id to that specific user's own id
    (plus action/entity_type/actor_name) - never a global count of the action name. An
    unrelated account_deactivated event belonging to some other user must never make
    either target's count look satisfied, and must never make the overall result look ok
    if a target's own event is missing, duplicated, or misattributed."""
    target_active_flags = {}
    target_audit_event_counts: Dict[str, int] = {}
    for uname in TARGET_USERNAMES:
        row = db.query(User).filter(User.username == uname).first()
        target_active_flags[uname] = row.is_active if row is not None else None
        target_audit_event_counts[uname] = (
            _count_matching_deactivation_audit_events(db, row.id) if row is not None else 0
        )

    protected_admins = (
        db.query(User.username)
        .filter(User.username.in_(PROTECTED_ADMIN_USERNAMES), User.role == "admin", User.is_active == True)  # noqa: E712
        .order_by(User.username)
        .all()
    )
    return PostApplyCheckResult(
        target_active_flags=target_active_flags,
        protected_admin_usernames=[u.username for u in protected_admins],
        target_audit_event_counts=target_audit_event_counts,
    )


def run_post_apply_check(engine) -> bool:
    """Read-only verification of the *result* of a completed (or ambiguous, see
    COMMIT_OUTCOME_UNKNOWN) apply. Never writes, always rolls back."""
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
        print(f"target_active_flags: {result.target_active_flags} (expected all False)")
        print(f"protected_admin_usernames: {result.protected_admin_usernames}")
        print(
            f"target_audit_event_counts: {result.target_audit_event_counts} "
            f"(expected 1 for each of {list(TARGET_USERNAMES)})"
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
        help="Read-only: verify both targets are inactive, both protected admin accounts "
             "are unaffected, and exactly one correctly-attributed deactivation audit "
             "event exists per target. Does not apply anything.",
    )
    args = parser.parse_args()

    try:
        engine = create_engine(settings.database_url)
    except Exception as e:
        print(f"ENGINE_SETUP_FAILED: {_safe_failure_message(e)}", file=sys.stderr)
        return 1

    if args.post_check:
        ok = run_post_apply_check(engine)
        return 0 if ok else 1

    if not args.apply:
        ok = run_dry_run(engine)
        return 0 if ok else 1

    # --apply path: verify the target before touching anything.
    if not run_pre_apply_check(engine):
        print("REFUSING: target verification failed - no changes made.", file=sys.stderr)
        return 1

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        result = run_apply(db, settings.environment)
    finally:
        db.close()

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
    print(f"APPLY_OK: deactivated {', '.join(TARGET_USERNAMES)}; 2 audit events committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
