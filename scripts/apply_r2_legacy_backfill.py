#!/usr/bin/env python3
"""R2c: apply the legacy backfill planned (read-only) by R2b's plan_r2_legacy_backfill.py.

Three modes, mutually exclusive:
  - default: read-only dry-run - the exact same plan as R2b (reused directly from
    scripts/plan_r2_legacy_backfill.py, not reimplemented), plus PLAN_FINGERPRINT and
    PROTECTED_STATE_FINGERPRINT.
  - --apply --expected-plan-fingerprint <hex64> --expected-protected-state-fingerprint
    <hex64>: performs the backfill, once, in a single transaction.
  - --post-check --expected-protected-state-fingerprint <hex64>: read-only verification
    of the result of a completed (or ambiguous) apply.

Deployment note: this script imports its sibling scripts/plan_r2_legacy_backfill.py by
its full package path (scripts.plan_r2_legacy_backfill), and services.api.models/config
by their normal path. Both require the *whole* repository tree (services/ next to
scripts/) to be mounted read-only together - mounting this single file alone, the way
some earlier one-off scripts were mounted, is not enough for this one.

What --apply does, all in one transaction, in this exact order:
  0. SET LOCAL lock_timeout to a short fixed time, then LOCK TABLE ... IN SHARE ROW
     EXCLUSIVE MODE on every table this operation reads or writes, in one fixed order
     (see LOCK_TABLES_IN_ORDER). This mode still allows ordinary reads to proceed
     concurrently, but blocks any concurrent INSERT/UPDATE/DELETE against these tables
     until this transaction ends - closing the window between "we decided what to do"
     and "we did it" that a bare fingerprint check alone cannot close on its own
     (fingerprints prove nothing changed *before* this point; locks prevent anything
     from changing *after* it, for the rest of this transaction). Only after the locks
     are held does this function look at the data at all - target/plan validity and
     both fingerprints are (re-)checked fresh, from inside the locked state.
  1. responsible_user_id = andrei.sakki.id on every currently-NULL row in pressure_tests,
     planned_test_lists, pressure_test_records - each UPDATE itself is additionally
     scoped `WHERE id = :id AND responsible_user_id IS NULL` and required to affect
     exactly one row, so even the locked, single-writer window still never overwrites a
     row that turns out to already have a responsible_user_id.
  2. One new Gauge per normalized (trim + uppercase) non-blank legacy metadata_json.
     wika_nr group. Gauge.serial_number is the group's own canonical trim()'d raw value
     - never force-cased - which is safe specifically because PLAN_OK already requires
     formatting_conflict_group_count == 0, so every group has exactly one raw variant by
     the time --apply is allowed to run at all.
  3. gauge_id + gauge_serial_snapshot (copied verbatim from the linked Gauge's own
     serial_number) on every TestRevision whose wika_nr is non-blank - each UPDATE is
     scoped `WHERE id = :id AND gauge_id IS NULL AND gauge_serial_snapshot IS NULL` and
     required to affect exactly one row, so an already-linked revision is never
     silently overwritten.
  4. metadata_json itself is never written to, by any of the above - it is only ever
     read.
  5. Exactly one audit event per mutation, all in the same transaction:
     legacy_responsibility_assigned (per top-level row), legacy_gauge_created (per new
     Gauge), legacy_gauge_linked (per revision). AuditEvent.user_id is never set to
     andrei's id or any other id - that column means "the human who submitted this
     request as themselves" (see R1c's semantic map), and this is a script-driven bulk
     operation, not a session - so it stays NULL, exactly like the R1c/bootstrap
     scripts' own audit events, and actor_name carries a fixed, safe, non-secret label
     instead.

Safety model:
  - verify_target() + the *full* R2b run_plan() must both report ok=True, re-computed
    fresh inside the write transaction, after the locks are held - not merely re-checked
    at dry-run time. This is the same "verify twice" discipline as the bootstrap/
    deactivate scripts, generalized: here the second verification is the entire plan,
    not just a handful of account-state booleans, because what --apply is allowed to
    touch depends on the full data shape, not just a few flags. R2b's own run_plan() now
    also refuses (PLAN_OK=False) if responsible_user_id is already set to ANYONE on any
    target row, including andrei.sakki - before the first R2c apply, every one of those
    must be NULL, not "NULL or already correct".
  - Two independent fingerprints, both required for --apply, both re-verified fresh
    after the locks are held:
      * PROTECTED_STATE_FINGERPRINT (compute_protected_state_fingerprint()): a SHA-256
        over the exact (row id, exact value - including NULL) pairs for every
        PROTECTED_COLUMNS cell, the full metadata_json of every TestRevision, andrei.
        sakki's own id/active/role state, and every audit_event whose action is NOT one
        of the three R2c actions. This is what makes "R2a's protected fields must be
        untouched" a provable, exact-value guarantee rather than a null/non-null count
        that a same-count swap between two rows could slip past undetected.
      * PLAN_FINGERPRINT (compute_plan_fingerprint()): a SHA-256 over the exact set of
        target row ids for responsibility assignment, the exact set of (normalized,
        canonical-raw) gauge serial pairs (not just the uppercased group key - a
        case/whitespace-only change to a serial changes this), the exact metadata_json
        of every eligible revision, andrei's own id, and the protected-state fingerprint
        itself - so a change to anything the protected-state fingerprint covers also
        changes this one.
    Neither fingerprint's own hex output can be reversed back into the ids/serials/
    values that fed it.
  - Re-running --apply after a completed success is refused by the same PLAN_OK gate
    that a first run required: gauges is no longer empty (and responsible_user_id is no
    longer NULL anywhere), so R2b's own stop conditions fire on the second run's fresh
    plan - no separate "already applied" bookkeeping is needed.
  - Before the very first apply, exactly zero audit_events may already use one of the
    three R2c action names, regardless of actor_name - even one is a stop condition (see
    _check_no_preexisting_r2c_audit_events()), since it would mean either a prior partial
    apply left artifacts, or something else collided with these reserved names.
  - ABORTED_BEFORE_COMMIT (safe to roll back, safe to report "nothing changed") is never
    conflated with COMMIT_OUTCOME_UNKNOWN (never rolled back, never retried blindly -
    the operator is told to run --post-check and stop). A lock_timeout failure is just
    another exception raised before commit, so it is reported as ABORTED_BEFORE_COMMIT
    like any other pre-commit failure - see run_apply().
  - Never prints a UUID, Log No., real gauge serial number, metadata_json content,
    password, hash, or connection string - including on failure: unexpected exceptions
    are reported only by exception class name (see _safe_failure_message()).
"""
import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Import the sibling R2b planner by its full package path (scripts.plan_r2_legacy_backfill)
# rather than as a bare top-level module, so pytest (which already imports it that way)
# and this script always share exactly one module object / one set of dataclasses - see
# the module docstring's deployment note for what that requires at runtime.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.plan_r2_legacy_backfill import (  # noqa: E402
    ANDREI_USERNAME,
    EXPECTED_ALEMBIC_HEAD,
    EXPECTED_ARDOR_ENV,
    EXPECTED_DATABASE_NAME,
    PROTECTED_COLUMNS,
    RESPONSIBILITY_TABLES,
    PlanResult,
    compute_audit_events_control_count,
    compute_protected_column_stats,
    run_plan,
    _print_plan as _print_r2b_plan,
)
from services.api.config import settings  # noqa: E402
from services.api.models import AuditEvent, Gauge, User  # noqa: E402

ACTOR_LABEL = "r2c_legacy_backfill_script (owner-authorized, out-of-band)"
RESPONSIBILITY_ACTION = "legacy_responsibility_assigned"
GAUGE_CREATED_ACTION = "legacy_gauge_created"
GAUGE_LINKED_ACTION = "legacy_gauge_linked"
R2C_ACTIONS = (RESPONSIBILITY_ACTION, GAUGE_CREATED_ACTION, GAUGE_LINKED_ACTION)
ENTITY_TYPE_BY_TABLE = {
    "pressure_tests": "pressure_test",
    "planned_test_lists": "planned_test_list",
    "pressure_test_records": "pressure_test_record",
}
EXPECTED_REASON_BY_ACTION = {
    RESPONSIBILITY_ACTION: "R2c legacy backfill: responsible_user_id assigned to andrei.sakki",
    GAUGE_CREATED_ACTION: "R2c legacy backfill: created from legacy wika_nr",
    GAUGE_LINKED_ACTION: "R2c legacy backfill: linked to legacy Gauge",
}
# The exact details_json object each action's audit event must have - not merely a
# 'reason' substring match, so an event with an extra/renamed/changed key is caught.
# json.dumps() with sort_keys is not needed here: each object has exactly one key, so
# there is only one possible serialization, and it is compared via a Postgres jsonb ==
# jsonb equality (parsed-structure equality, not string equality) - see
# _entity_id_set_and_cardinality_problems().
EXPECTED_DETAILS_JSON_BY_ACTION = {
    action: json.dumps({"reason": reason}) for action, reason in EXPECTED_REASON_BY_ACTION.items()
}
NONBLANK_WIKA_NR_PREDICATE = (
    "metadata_json::jsonb ? 'wika_nr' AND trim(metadata_json->>'wika_nr') != ''"
)

# Tables locked, in this fixed order, at the very start of apply_backfill() - before any
# read, let alone any write. SHARE ROW EXCLUSIVE allows ordinary SELECTs to continue
# concurrently but blocks any concurrent INSERT/UPDATE/DELETE on these tables until this
# transaction commits or rolls back.
LOCK_TABLES_IN_ORDER = (
    "alembic_version", "users", "pressure_tests", "planned_test_lists",
    "pressure_test_records", "test_revisions", "gauges", "audit_events",
)
LOCK_TIMEOUT_MS = 5000

_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}\Z")


class ApplyTargetError(RuntimeError):
    """Raised when target/plan validity fails before any mutation. Message text is
    always safe to print - it is built only from R2b's own already-sanitized problem
    strings, or from counts/table names."""


class FingerprintMismatchError(RuntimeError):
    """Raised when a freshly-recomputed fingerprint does not match the corresponding
    --expected-*-fingerprint. Message text is always safe to print: fingerprints are
    SHA-256 hex digests, which cannot be reversed back into the ids/serials/values that
    fed them."""


class ApplyPostconditionError(RuntimeError):
    """Raised if the operation's own result does not look exactly as expected,
    immediately before commit. Message text is always safe to print - built only from
    table/column names and counts, never row content."""


def _safe_failure_message(exc: BaseException) -> str:
    """Never surface a raw exception's full text for anything outside this script's own
    controlled error types - SQLAlchemy/psycopg2 exceptions often embed the failing SQL
    statement and its bound parameters (which may include a UUID or a gauge serial) in
    str(exc). This also covers a lock_timeout failure (psycopg2's LockNotAvailable is
    not one of this script's controlled types), so it is redacted the same way."""
    if isinstance(exc, (ApplyTargetError, FingerprintMismatchError, ApplyPostconditionError)):
        return str(exc)
    return f"{type(exc).__name__} (details withheld: may contain SQL text/parameters)"


def _fingerprint_arg_type(value: str) -> str:
    """argparse `type=` validator: rejects anything that is not exactly 64 lowercase hex
    characters before argparse even returns from parse_args() - i.e. before main() does
    anything else, including before create_engine() ever runs."""
    if not _FINGERPRINT_RE.match(value):
        raise argparse.ArgumentTypeError("must be exactly 64 lowercase hex characters (a SHA-256 digest)")
    return value


# --- table locks: close the TOCTOU window between "decide" and "act" ----------------

def _acquire_table_locks(db: Session) -> None:
    db.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT_MS}ms';"))
    for table in LOCK_TABLES_IN_ORDER:
        db.execute(text(f'LOCK TABLE "{table}" IN SHARE ROW EXCLUSIVE MODE;'))


def _check_no_preexisting_r2c_audit_events(db: Session) -> int:
    """Returns the count of audit_events already using one of the three R2c action
    names, regardless of actor_name. Even one is a stop condition."""
    return db.execute(
        text("SELECT count(*) FROM audit_events WHERE action = ANY(:actions);"),
        {"actions": list(R2C_ACTIONS)},
    ).scalar()


# --- PROTECTED_STATE_FINGERPRINT ------------------------------------------------------

def _enc(value) -> str:
    """Length-prefixed, unambiguous encoding of a single scalar: None maps to the
    literal sentinel "N" (which can never collide with a length-prefixed real value,
    since those always start with a decimal digit followed by ':'), everything else is
    rendered as "<byte-length>:<value>" so that NULL, the empty string, and any string
    containing digits/colons/pipes are all distinguishable from one another and from
    each other's encodings."""
    if value is None:
        return "N"
    s = str(value)
    b = s.encode("utf-8")
    return f"{len(b)}:{s}"


def compute_protected_state_fingerprint(db: Session, andrei_id: str) -> str:
    """SHA-256 over exactly what must remain untouched by --apply:
      - every (row id, exact value including NULL) pair for every PROTECTED_COLUMNS cell
      - the full metadata_json of every TestRevision
      - andrei.sakki's own id, is_active, and role
      - every audit_event whose action is NOT one of the three R2c actions
    Rows within each group are ordered by id for a deterministic, order-independent
    result. Only the resulting hex digest is ever returned or printed."""
    parts: List[str] = []

    for table, column in PROTECTED_COLUMNS:
        rows = db.execute(text(f'SELECT id, "{column}" FROM "{table}" ORDER BY id;')).fetchall()
        for row_id, value in rows:
            parts.append(f"col|{table}|{column}|{_enc(row_id)}|{_enc(value)}")

    rev_rows = db.execute(text("SELECT id, metadata_json::text FROM test_revisions ORDER BY id;")).fetchall()
    for rev_id, meta in rev_rows:
        parts.append(f"metadata|{_enc(rev_id)}|{_enc(meta)}")

    andrei = db.query(User).filter(User.username == ANDREI_USERNAME).first()
    parts.append(
        "andrei|" + _enc(andrei.id if andrei else None)
        + "|" + _enc(andrei.is_active if andrei else None)
        + "|" + _enc(andrei.role if andrei else None)
    )

    audit_rows = db.execute(
        text("""
            SELECT id, user_id, actor_name, action, entity_type, entity_id,
                   details_json::text, created_at::text
            FROM audit_events
            WHERE NOT (action = ANY(:actions))
            ORDER BY id;
        """),
        {"actions": list(R2C_ACTIONS)},
    ).fetchall()
    for row in audit_rows:
        parts.append("audit|" + "|".join(_enc(v) for v in row))

    blob = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# --- PLAN_FINGERPRINT ----------------------------------------------------------------

def compute_plan_fingerprint(db: Session, andrei_id: str, protected_state_fingerprint: str) -> str:
    """SHA-256 over exactly what --apply must still match to proceed safely: the full
    sorted set of target row ids for responsibility assignment (per table), the exact
    set of (normalized, canonical-raw) gauge serial pairs - not just the uppercased
    group key, so a case/whitespace-only change to a serial changes this - the exact
    metadata_json of every eligible revision, a canonical snapshot of every protected/
    control count, andrei's own id, and the protected-state fingerprint itself (so
    anything that fingerprint covers also changes this one). Only the resulting hex
    digest is ever returned or printed."""
    parts: List[str] = []

    for table in RESPONSIBILITY_TABLES:
        ids = [r[0] for r in db.execute(
            text(f'SELECT id FROM "{table}" WHERE responsible_user_id IS NULL ORDER BY id;')
        ).fetchall()]
        parts.append(f"{table}_null_ids:" + ",".join(ids))

    group_rows = db.execute(text(f"""
        SELECT upper(trim(metadata_json->>'wika_nr')) AS norm, trim(metadata_json->>'wika_nr') AS canonical
        FROM test_revisions WHERE {NONBLANK_WIKA_NR_PREDICATE}
        GROUP BY norm, canonical ORDER BY norm, canonical;
    """)).fetchall()
    parts.append("gauge_groups:" + ",".join(f"{_enc(norm)}={_enc(canonical)}" for norm, canonical in group_rows))

    eligible_rows = db.execute(text(f"""
        SELECT id, metadata_json::text FROM test_revisions
        WHERE {NONBLANK_WIKA_NR_PREDICATE} ORDER BY id;
    """)).fetchall()
    parts.append("eligible_revisions:" + ",".join(f"{_enc(rid)}={_enc(meta)}" for rid, meta in eligible_rows))

    for table, column in PROTECTED_COLUMNS:
        stats = compute_protected_column_stats(db, table, column)
        parts.append(f"{table}.{column}:{stats.non_null_count}:{stats.null_count}")

    parts.append(f"audit_events:{compute_audit_events_control_count(db)}")
    parts.append(f"gauges_row_count:{db.execute(text('SELECT count(*) FROM gauges;')).scalar()}")
    parts.append(f"andrei_id:{_enc(andrei_id)}")
    parts.append(f"protected_state_fingerprint:{protected_state_fingerprint}")

    blob = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _compute_both_fingerprints(db: Session) -> "tuple[str, str, Optional[str]]":
    """Returns (plan_fingerprint, protected_state_fingerprint, andrei_id). andrei_id may
    be None if andrei.sakki does not exist yet - callers that need a valid target should
    have already checked target.ok (which requires andrei to exist) before calling this."""
    andrei = db.query(User).filter(User.username == ANDREI_USERNAME).first()
    andrei_id = andrei.id if andrei else None
    protected_state_fingerprint = compute_protected_state_fingerprint(db, andrei_id)
    plan_fingerprint = compute_plan_fingerprint(db, andrei_id, protected_state_fingerprint)
    return plan_fingerprint, protected_state_fingerprint, andrei_id


# --- apply --------------------------------------------------------------------------

@dataclass
class ApplyResult:
    responsibility_assigned_by_table: Dict[str, int]
    gauges_created: int
    revisions_linked: int
    audit_events_added: int


def _entity_id_set_and_cardinality_problems(
    db: Session, action: str, entity_type: str, expected_entity_ids: List[str],
) -> List[str]:
    """Groups fully-correct-shaped events (action, entity_type, actor_name=ACTOR_LABEL,
    user_id IS NULL, details_json exactly equal - as parsed JSON, not a substring - to
    the one expected object for this action) by entity_id, then compares the resulting
    {entity_id: count} map against expected_entity_ids as a set-plus-cardinality check:
    every expected id must appear with count exactly 1, no expected id may be missing,
    and no fully-correct event may exist for an id outside the expected set.

    This is deliberately independent of any aggregate COUNT(*): one missing expected id
    and one duplicated expected id can leave an aggregate total unchanged (e.g. 2 events
    for 2 expected ids, but one id has 0 and the other has 2) - a case an aggregate count
    alone cannot distinguish from "everything is correct", but this GROUP BY can."""
    rows = db.execute(
        text("""
            SELECT entity_id, count(*) FROM audit_events
            WHERE action = :action AND entity_type = :entity_type AND actor_name = :actor_name
              AND user_id IS NULL AND details_json::jsonb = (:expected_details_json)::jsonb
            GROUP BY entity_id;
        """),
        # The parens around (:expected_details_json) are required, not decorative:
        # SQLAlchemy's text() does not recognize a bind parameter immediately followed
        # by '::' as a parameter at all (it special-cases '::' for Postgres cast syntax),
        # so ":expected_details_json::jsonb" silently reaches the server as literal,
        # unbound text and fails - confirmed against a real Postgres server.
        {
            "action": action, "entity_type": entity_type, "actor_name": ACTOR_LABEL,
            "expected_details_json": EXPECTED_DETAILS_JSON_BY_ACTION[action],
        },
    ).fetchall()
    counts_by_entity_id = {row[0]: row[1] for row in rows}
    expected_set = set(expected_entity_ids)
    actual_set = set(counts_by_entity_id.keys())

    missing = expected_set - actual_set
    unexpected = actual_set - expected_set
    duplicated = {eid for eid in expected_set & actual_set if counts_by_entity_id[eid] != 1}

    problems: List[str] = []
    if missing:
        problems.append(f"{action}/{entity_type}: {len(missing)} expected entity id(s) have no fully-correct event")
    if unexpected:
        problems.append(
            f"{action}/{entity_type}: {len(unexpected)} fully-correct event(s) exist for unexpected entity id(s)"
        )
    if duplicated:
        problems.append(
            f"{action}/{entity_type}: {len(duplicated)} expected entity id(s) have more than one fully-correct event"
        )
    return problems


def _verify_r2c_audit_events_exact(
    db: Session, action: str, entity_type: str, expected_entity_ids: List[str],
) -> List[str]:
    """Full verification for a single-entity_type R2c action (legacy_gauge_created,
    legacy_gauge_linked - legacy_responsibility_assigned spans three entity_types and is
    verified by calling _entity_id_set_and_cardinality_problems() once per table instead,
    alongside its own separate global total-count check - see apply_backfill() and
    run_post_check_logic()). Three independent checks, all required:
      1. The TOTAL count of audit_events with this action must equal exactly the number
         of expected entity ids - an independent aggregate check, kept alongside (not
         instead of) the exact per-entity_id check below, since together they catch
         cases neither alone would (e.g. an extra event under a *different*, unexpected
         action-sharing entity_type is invisible to the per-entity_id check below but
         changes this total).
      2. No event with this action has a non-NULL user_id (this column means "the human
         who submitted this request as themselves" - never true for a script-driven bulk
         operation, see the module docstring).
      3. _entity_id_set_and_cardinality_problems(): every expected entity_id has exactly
         one fully-correct event, no expected id is missing, no fully-correct event
         exists for an unexpected id.
    """
    problems: List[str] = []

    total_count = db.execute(
        text("SELECT count(*) FROM audit_events WHERE action = :action;"), {"action": action}
    ).scalar()
    if total_count != len(expected_entity_ids):
        problems.append(f"{action}: total event count is {total_count}, expected exactly {len(expected_entity_ids)}")

    wrong_user_id_count = db.execute(
        text("SELECT count(*) FROM audit_events WHERE action = :action AND user_id IS NOT NULL;"),
        {"action": action},
    ).scalar()
    if wrong_user_id_count:
        problems.append(f"{action}: {wrong_user_id_count} event(s) have a non-NULL user_id")

    problems.extend(_entity_id_set_and_cardinality_problems(db, action, entity_type, expected_entity_ids))
    return problems


# --- Gauge invariants: one shared computation for both apply_backfill()'s pre-commit
#     postcondition and the standalone --post-check, so the two can never drift apart -

# NONBLANK_WIKA_NR_PREDICATE itself is only ever used in a positive `WHERE <predicate>`
# position, where SQL's three-valued logic already does the right thing: a predicate
# that evaluates to NULL (not just FALSE) is excluded from the result either way, so a
# revision is correctly never treated as eligible when metadata_json has
# `"wika_nr": null` (a JSON null value - `->>'wika_nr'` on that returns SQL NULL, so
# `trim(NULL) != ''` is NULL, and `TRUE AND NULL` is NULL). But that same NULL is a
# trap for the *complement* (`WHERE NOT (<predicate>)`): `NOT NULL` is NULL too, not
# TRUE, so a naive complement would ALSO exclude that same revision from the
# "noneligible" side - meaning a wika_nr:null revision with a gauge_id/snapshot
# incorrectly set could satisfy neither the eligible-link check nor the noneligible
# check, and the error would go undetected. NONELIGIBLE_WIKA_NR_PREDICATE fixes this by
# coalescing the inner predicate to boolean false before negating it, so every one of
# missing-key / JSON-null / blank / whitespace-only maps unambiguously to "noneligible".
NONELIGIBLE_WIKA_NR_PREDICATE = f"NOT COALESCE(({NONBLANK_WIKA_NR_PREDICATE}), false)"


@dataclass
class GaugeInvariantStats:
    gauge_group_count: int
    gauges_row_count: int
    gauge_groups_match_gauges: bool
    partial_gauge_pair_count: int
    inconsistent_link_count: int
    unexpected_noneligible_gauge_pair_count: int
    inactive_gauge_count: int
    gauge_serial_set_matches: bool

    @property
    def ok(self) -> bool:
        return (
            self.gauge_groups_match_gauges
            and self.partial_gauge_pair_count == 0
            and self.inconsistent_link_count == 0
            and self.unexpected_noneligible_gauge_pair_count == 0
            and self.inactive_gauge_count == 0
            and self.gauge_serial_set_matches
        )

    def safe_problem_summary(self) -> List[str]:
        """Safe (counts/booleans only, no ids/serials) description of every failing
        sub-check - used both by apply_backfill()'s ApplyPostconditionError message and
        by callers that want a human-readable summary without re-deriving it."""
        problems: List[str] = []
        if not self.gauge_groups_match_gauges:
            problems.append(f"gauge_group_count={self.gauge_group_count} != gauges_row_count={self.gauges_row_count}")
        if self.partial_gauge_pair_count:
            problems.append(f"partial_gauge_pair_count={self.partial_gauge_pair_count}")
        if self.inconsistent_link_count:
            problems.append(f"inconsistent_link_count={self.inconsistent_link_count}")
        if self.unexpected_noneligible_gauge_pair_count:
            problems.append(f"unexpected_noneligible_gauge_pair_count={self.unexpected_noneligible_gauge_pair_count}")
        if self.inactive_gauge_count:
            problems.append(f"inactive_gauge_count={self.inactive_gauge_count}")
        if not self.gauge_serial_set_matches:
            problems.append("gauge_serial_set_matches=False")
        return problems


def compute_gauge_invariant_stats(db: Session) -> GaugeInvariantStats:
    """The single source of truth for every Gauge-related invariant this backfill must
    hold, both immediately before commit (apply_backfill()) and independently afterward
    (run_post_check_logic()) - one shared computation so the two can never quietly
    diverge from each other."""
    gauge_group_count = db.execute(text(f"""
        SELECT count(DISTINCT upper(trim(metadata_json->>'wika_nr')))
        FROM test_revisions WHERE {NONBLANK_WIKA_NR_PREDICATE};
    """)).scalar()
    gauges_row_count = db.execute(text("SELECT count(*) FROM gauges;")).scalar()

    partial_gauge_pair_count = db.execute(text("""
        SELECT count(*) FROM test_revisions
        WHERE (gauge_id IS NOT NULL AND gauge_serial_snapshot IS NULL)
           OR (gauge_id IS NULL AND gauge_serial_snapshot IS NOT NULL);
    """)).scalar()

    inconsistent_link_count = db.execute(text(f"""
        SELECT count(*) FROM test_revisions tr
        LEFT JOIN gauges g ON g.id = tr.gauge_id
        WHERE {NONBLANK_WIKA_NR_PREDICATE}
          AND (tr.gauge_id IS NULL OR tr.gauge_serial_snapshot IS NULL OR g.id IS NULL
               OR tr.gauge_serial_snapshot IS DISTINCT FROM trim(tr.metadata_json->>'wika_nr')
               OR g.serial_number IS DISTINCT FROM trim(tr.metadata_json->>'wika_nr'));
    """)).scalar()

    unexpected_noneligible_gauge_pair_count = db.execute(text(f"""
        SELECT count(*) FROM test_revisions
        WHERE {NONELIGIBLE_WIKA_NR_PREDICATE}
          AND (gauge_id IS NOT NULL OR gauge_serial_snapshot IS NOT NULL);
    """)).scalar()

    inactive_gauge_count = db.execute(text("SELECT count(*) FROM gauges WHERE is_active = false;")).scalar()

    expected_serial_set = {
        r[0] for r in db.execute(text(f"""
            SELECT DISTINCT trim(metadata_json->>'wika_nr') FROM test_revisions
            WHERE {NONBLANK_WIKA_NR_PREDICATE};
        """)).fetchall()
    }
    actual_serial_set = {r[0] for r in db.execute(text("SELECT serial_number FROM gauges;")).fetchall()}
    gauge_serial_set_matches = (expected_serial_set == actual_serial_set)

    return GaugeInvariantStats(
        gauge_group_count=gauge_group_count,
        gauges_row_count=gauges_row_count,
        gauge_groups_match_gauges=(gauge_group_count == gauges_row_count),
        partial_gauge_pair_count=partial_gauge_pair_count,
        inconsistent_link_count=inconsistent_link_count,
        unexpected_noneligible_gauge_pair_count=unexpected_noneligible_gauge_pair_count,
        inactive_gauge_count=inactive_gauge_count,
        gauge_serial_set_matches=gauge_serial_set_matches,
    )


def apply_backfill(
    db: Session, environment: str,
    expected_plan_fingerprint: str, expected_protected_state_fingerprint: str,
) -> ApplyResult:
    """Performs the entire R2c backfill on the given session. Does NOT call db.commit()
    or db.rollback() - that is the caller's responsibility (see run_apply()), so a
    single external transaction boundary covers everything this function does.

    Raises ApplyTargetError / FingerprintMismatchError (nothing written yet - the table
    locks taken at the very start are released by the caller's rollback like any other
    lock held in an aborted transaction) if the fresh target+plan check, the
    preexisting-R2c-audit-event check, or either fingerprint comparison fails, or
    ApplyPostconditionError (still nothing committed - caller must roll back) if the
    result immediately before return does not look exactly as expected.
    """
    # --- 0. locks first: nothing below reads or writes anything before this ----------
    _acquire_table_locks(db)

    preexisting = _check_no_preexisting_r2c_audit_events(db)
    if preexisting:
        raise ApplyTargetError(
            f"Refusing to apply: {preexisting} audit_event(s) already use one of the "
            f"three reserved R2c action names - this must be exactly 0 before the first apply."
        )

    plan = run_plan(db, environment)
    if not plan.ok:
        reasons = plan.target.problems if not plan.target.ok else plan.problems
        raise ApplyTargetError("Refusing to apply: PLAN_OK is False. Reasons: " + "; ".join(reasons))

    plan_fingerprint, protected_state_fingerprint, andrei_id = _compute_both_fingerprints(db)

    if protected_state_fingerprint != expected_protected_state_fingerprint:
        raise FingerprintMismatchError(
            "Refusing to apply: protected-state fingerprint mismatch - protected data "
            "changed since the dry-run that produced --expected-protected-state-fingerprint. "
            f"expected={expected_protected_state_fingerprint} actual={protected_state_fingerprint}"
        )
    if plan_fingerprint != expected_plan_fingerprint:
        raise FingerprintMismatchError(
            "Refusing to apply: plan fingerprint mismatch - the underlying data changed "
            "since the dry-run that produced --expected-plan-fingerprint (or a stale "
            "fingerprint was supplied). "
            f"expected={expected_plan_fingerprint} actual={plan_fingerprint}"
        )

    audit_events_added = 0

    # --- 1. responsible_user_id assignment - each UPDATE re-checks IS NULL itself ---
    responsibility_touched: Dict[str, List[str]] = {}
    for table in RESPONSIBILITY_TABLES:
        ids = [r[0] for r in db.execute(
            text(f'SELECT id FROM "{table}" WHERE responsible_user_id IS NULL ORDER BY id;')
        ).fetchall()]
        for row_id in ids:
            result = db.execute(
                text(
                    f'UPDATE "{table}" SET responsible_user_id = :andrei_id '
                    f'WHERE id = :row_id AND responsible_user_id IS NULL;'
                ),
                {"andrei_id": andrei_id, "row_id": row_id},
            )
            if result.rowcount != 1:
                raise ApplyPostconditionError(
                    f"Refusing: responsible_user_id UPDATE on '{table}' affected "
                    f"{result.rowcount} row(s), expected exactly 1 (concurrent modification detected)."
                )
            db.add(AuditEvent(
                action=RESPONSIBILITY_ACTION,
                entity_type=ENTITY_TYPE_BY_TABLE[table],
                entity_id=row_id,
                actor_name=ACTOR_LABEL,
                details_json={"reason": EXPECTED_REASON_BY_ACTION[RESPONSIBILITY_ACTION]},
            ))
            audit_events_added += 1
        responsibility_touched[table] = ids

    # --- 2. one Gauge per normalized group ---
    # PLAN_OK already guarantees formatting_conflict_group_count == 0, so this GROUP BY
    # is guaranteed to yield exactly one canonical raw value per normalized group - it
    # confirms that guarantee, it does not itself resolve a conflict.
    group_rows = db.execute(text(f"""
        SELECT upper(trim(metadata_json->>'wika_nr')) AS norm, trim(metadata_json->>'wika_nr') AS canonical
        FROM test_revisions WHERE {NONBLANK_WIKA_NR_PREDICATE}
        GROUP BY norm, canonical ORDER BY norm;
    """)).fetchall()

    gauge_id_by_norm: Dict[str, str] = {}
    for norm, canonical in group_rows:
        gauge = Gauge(serial_number=canonical, is_active=True)
        db.add(gauge)
        db.flush()  # assign gauge.id before the audit event below needs it
        gauge_id_by_norm[norm] = gauge.id
        db.add(AuditEvent(
            action=GAUGE_CREATED_ACTION, entity_type="gauge", entity_id=gauge.id,
            actor_name=ACTOR_LABEL,
            details_json={"reason": EXPECTED_REASON_BY_ACTION[GAUGE_CREATED_ACTION]},
        ))
        audit_events_added += 1

    # --- 3. link eligible revisions to their Gauge - each UPDATE re-checks NULL pair -
    eligible_revs = db.execute(text(f"""
        SELECT id, upper(trim(metadata_json->>'wika_nr')) AS norm, trim(metadata_json->>'wika_nr') AS canonical
        FROM test_revisions WHERE {NONBLANK_WIKA_NR_PREDICATE} ORDER BY id;
    """)).fetchall()

    for rev_id, norm, canonical in eligible_revs:
        result = db.execute(
            text(
                "UPDATE test_revisions SET gauge_id = :gauge_id, gauge_serial_snapshot = :snapshot "
                "WHERE id = :rev_id AND gauge_id IS NULL AND gauge_serial_snapshot IS NULL;"
            ),
            {"gauge_id": gauge_id_by_norm[norm], "snapshot": canonical, "rev_id": rev_id},
        )
        if result.rowcount != 1:
            raise ApplyPostconditionError(
                f"Refusing: gauge-link UPDATE on 'test_revisions' affected {result.rowcount} row(s), "
                f"expected exactly 1 (an existing gauge_id/snapshot pair or concurrent modification detected)."
            )
        db.add(AuditEvent(
            action=GAUGE_LINKED_ACTION, entity_type="test_revision", entity_id=rev_id,
            actor_name=ACTOR_LABEL,
            details_json={"reason": EXPECTED_REASON_BY_ACTION[GAUGE_LINKED_ACTION]},
        ))
        audit_events_added += 1

    db.flush()

    # --- postconditions, immediately before returning to the caller for commit ------

    for table in RESPONSIBILITY_TABLES:
        mismatched = db.execute(
            text(f'SELECT count(*) FROM "{table}" WHERE responsible_user_id IS DISTINCT FROM :andrei_id;'),
            {"andrei_id": andrei_id},
        ).scalar()
        if mismatched != 0:
            raise ApplyPostconditionError(
                f"Post-check failed: '{table}' has {mismatched} row(s) whose responsible_user_id "
                f"is not exactly andrei.sakki's id."
            )

    # Every Gauge invariant (group/row-count match, no partial pairs, no inconsistent
    # eligible link, no Gauge wrongly linked to a noneligible revision, no inactive
    # Gauge, exact serial SET match) - computed by the same shared helper the standalone
    # --post-check uses, so the two can never quietly diverge. Checked here, before
    # commit, so a violation is a full rollback (ApplyPostconditionError), not merely a
    # later --post-check finding.
    gauge_stats = compute_gauge_invariant_stats(db)
    if not gauge_stats.ok:
        raise ApplyPostconditionError(
            "Post-check failed: Gauge invariant violation(s): " + "; ".join(gauge_stats.safe_problem_summary())
        )

    all_responsibility_ids = [i for ids in responsibility_touched.values() for i in ids]
    # Responsibility events span three different entity_types (one per table), so the
    # exact-match half of the check must run per table (entity_type differs), while the
    # total-count half must run once globally across all three tables combined (they
    # all share the same action name).
    total_responsibility_count = db.execute(
        text("SELECT count(*) FROM audit_events WHERE action = :action;"), {"action": RESPONSIBILITY_ACTION}
    ).scalar()
    if total_responsibility_count != len(all_responsibility_ids):
        raise ApplyPostconditionError(
            f"Post-check failed: {RESPONSIBILITY_ACTION} total event count is "
            f"{total_responsibility_count}, expected exactly {len(all_responsibility_ids)}."
        )
    wrong_user_id_count = db.execute(
        text("SELECT count(*) FROM audit_events WHERE action = :action AND user_id IS NOT NULL;"),
        {"action": RESPONSIBILITY_ACTION},
    ).scalar()
    if wrong_user_id_count:
        raise ApplyPostconditionError(f"Post-check failed: {RESPONSIBILITY_ACTION} has {wrong_user_id_count} event(s) with a non-NULL user_id.")
    for table, ids in responsibility_touched.items():
        table_problems = _entity_id_set_and_cardinality_problems(
            db, RESPONSIBILITY_ACTION, ENTITY_TYPE_BY_TABLE[table], ids
        )
        if table_problems:
            raise ApplyPostconditionError("Post-check failed: " + "; ".join(table_problems))

    gauge_ids = list(gauge_id_by_norm.values())
    gauge_problems = _verify_r2c_audit_events_exact(db, GAUGE_CREATED_ACTION, "gauge", gauge_ids)
    if gauge_problems:
        raise ApplyPostconditionError("Post-check failed: " + "; ".join(gauge_problems))

    rev_ids = [r[0] for r in eligible_revs]
    link_problems = _verify_r2c_audit_events_exact(db, GAUGE_LINKED_ACTION, "test_revision", rev_ids)
    if link_problems:
        raise ApplyPostconditionError("Post-check failed: " + "; ".join(link_problems))

    expected_audit_total = len(all_responsibility_ids) + len(group_rows) + len(eligible_revs)
    if audit_events_added != expected_audit_total:
        raise ApplyPostconditionError("Post-check failed: audit event count does not match the number of mutations performed.")

    # Final, cheapest-and-strongest check: recompute the protected-state fingerprint
    # after every mutation above. Since it deliberately excludes the three R2c actions
    # from its own audit_events component, and none of the mutations above touch any
    # PROTECTED_COLUMNS cell, metadata_json, or andrei's own row, this must come back
    # byte-for-byte identical to the value already verified before any mutation - any
    # difference means something protected moved that none of the more specific checks
    # above happened to catch.
    protected_state_after = compute_protected_state_fingerprint(db, andrei_id)
    if protected_state_after != protected_state_fingerprint:
        raise ApplyPostconditionError(
            "Post-check failed: protected-state fingerprint changed during apply - "
            "something outside this operation's intended scope was modified."
        )

    return ApplyResult(
        responsibility_assigned_by_table={t: len(ids) for t, ids in responsibility_touched.items()},
        gauges_created=len(group_rows),
        revisions_linked=len(eligible_revs),
        audit_events_added=audit_events_added,
    )


class ApplyOutcome(Enum):
    SUCCESS = "success"
    ABORTED_BEFORE_COMMIT = "aborted_before_commit"
    COMMIT_OUTCOME_UNKNOWN = "commit_outcome_unknown"


@dataclass
class ApplyRunResult:
    outcome: ApplyOutcome
    safe_message: Optional[str] = None
    summary: Optional[ApplyResult] = None


def run_apply(
    db: Session, environment: str,
    expected_plan_fingerprint: str, expected_protected_state_fingerprint: str,
) -> ApplyRunResult:
    """Runs apply_backfill() and db.commit() as two separately-handled steps, so a
    failure while staging the changes (including a lock_timeout failure right at the
    start) and a failure during commit are never conflated:

    - A failure from apply_backfill() happens strictly before commit is ever called;
      db.rollback() is guaranteed to fully revert it (and release the table locks) -
      ABORTED_BEFORE_COMMIT.
    - A failure from db.commit() itself gets no rollback call at all: the commit may
      have already reached the server, so "rolled back, nothing changed" would be a
      false claim - COMMIT_OUTCOME_UNKNOWN. The caller must not retry --apply blindly
      and must use --post-check (read-only) to determine the actual state.

    Never raises: every outcome comes back as an ApplyRunResult with an
    already-sanitized safe_message."""
    try:
        summary = apply_backfill(db, environment, expected_plan_fingerprint, expected_protected_state_fingerprint)
    except Exception as e:
        db.rollback()
        return ApplyRunResult(ApplyOutcome.ABORTED_BEFORE_COMMIT, _safe_failure_message(e))

    try:
        db.commit()
    except Exception as e:
        return ApplyRunResult(ApplyOutcome.COMMIT_OUTCOME_UNKNOWN, _safe_failure_message(e))

    return ApplyRunResult(ApplyOutcome.SUCCESS, summary=summary)


# --- post-check: read-only -----------------------------------------------------------

@dataclass
class PostCheckResult:
    responsibility_is_exactly_andrei_by_table: Dict[str, bool]
    gauge_group_count: int
    gauges_row_count: int
    gauge_groups_match_gauges: bool
    partial_gauge_pair_count: int
    inconsistent_link_count: int
    # Revisions with NO usable legacy wika_nr must have gauge_id/gauge_serial_snapshot
    # both NULL - a nonzero count here means something linked a Gauge to a revision this
    # backfill was never supposed to touch at all (partial_gauge_pair_count/
    # inconsistent_link_count above only ever look at *eligible* revisions).
    unexpected_noneligible_gauge_pair_count: int
    # Every Gauge this backfill creates is is_active=True; any inactive Gauge row means
    # something outside this operation's intended scope deactivated it.
    inactive_gauge_count: int
    # gauge_groups_match_gauges above is a cardinality-only check (same COUNT on both
    # sides could still hide the wrong serials); this proves the exact SET of
    # Gauge.serial_number values equals the exact set of canonical legacy wika_nr values
    # currently on eligible revisions - not just a matching count.
    gauge_serial_set_matches: bool
    audit_problems: List[str]
    protected_state_fingerprint_matches: bool
    protected_column_stats: List

    @property
    def ok(self) -> bool:
        return (
            all(self.responsibility_is_exactly_andrei_by_table.values())
            and self.gauge_groups_match_gauges
            and self.partial_gauge_pair_count == 0
            and self.inconsistent_link_count == 0
            and self.unexpected_noneligible_gauge_pair_count == 0
            and self.inactive_gauge_count == 0
            and self.gauge_serial_set_matches
            and not self.audit_problems
            and self.protected_state_fingerprint_matches
        )


def run_post_check_logic(db: Session, expected_protected_state_fingerprint: str) -> PostCheckResult:
    """Pure read-only query logic, factored out so it is directly testable without the
    PostgreSQL-only `BEGIN TRANSACTION READ ONLY` statement the CLI wrapper adds."""
    andrei = db.query(User).filter(User.username == ANDREI_USERNAME).first()
    andrei_id = andrei.id if andrei else None

    responsibility_is_exactly_andrei = {}
    for table in RESPONSIBILITY_TABLES:
        mismatched = db.execute(
            text(f'SELECT count(*) FROM "{table}" WHERE responsible_user_id IS DISTINCT FROM :andrei_id;'),
            {"andrei_id": andrei_id},
        ).scalar()
        responsibility_is_exactly_andrei[table] = (mismatched == 0)

    # Same shared computation apply_backfill() checks before commit - see
    # compute_gauge_invariant_stats()'s own docstring for why this must be one function,
    # not two independently-maintained copies.
    gauge_stats = compute_gauge_invariant_stats(db)

    audit_problems: List[str] = []

    all_responsibility_ids: List[str] = []
    for table in RESPONSIBILITY_TABLES:
        ids = [r[0] for r in db.execute(
            text(f'SELECT id FROM "{table}" WHERE responsible_user_id IS NOT DISTINCT FROM :andrei_id;'),
            {"andrei_id": andrei_id},
        ).fetchall()]
        all_responsibility_ids.extend(ids)
        audit_problems.extend(
            _entity_id_set_and_cardinality_problems(db, RESPONSIBILITY_ACTION, ENTITY_TYPE_BY_TABLE[table], ids)
        )

    total_responsibility_count = db.execute(
        text("SELECT count(*) FROM audit_events WHERE action = :action;"), {"action": RESPONSIBILITY_ACTION}
    ).scalar()
    if total_responsibility_count != len(all_responsibility_ids):
        audit_problems.append(
            f"{RESPONSIBILITY_ACTION}: total event count is {total_responsibility_count}, "
            f"expected exactly {len(all_responsibility_ids)}"
        )
    wrong_user_id_count = db.execute(
        text("SELECT count(*) FROM audit_events WHERE action = :action AND user_id IS NOT NULL;"),
        {"action": RESPONSIBILITY_ACTION},
    ).scalar()
    if wrong_user_id_count:
        audit_problems.append(f"{RESPONSIBILITY_ACTION}: {wrong_user_id_count} event(s) have a non-NULL user_id")

    gauge_ids = [r[0] for r in db.execute(text("SELECT id FROM gauges;")).fetchall()]
    audit_problems.extend(_verify_r2c_audit_events_exact(db, GAUGE_CREATED_ACTION, "gauge", gauge_ids))

    rev_ids = [r[0] for r in db.execute(text(f"SELECT id FROM test_revisions WHERE {NONBLANK_WIKA_NR_PREDICATE};")).fetchall()]
    audit_problems.extend(_verify_r2c_audit_events_exact(db, GAUGE_LINKED_ACTION, "test_revision", rev_ids))

    protected_state_fingerprint = compute_protected_state_fingerprint(db, andrei_id)
    protected_state_fingerprint_matches = (protected_state_fingerprint == expected_protected_state_fingerprint)

    protected_column_stats = [compute_protected_column_stats(db, t, c) for t, c in PROTECTED_COLUMNS]

    return PostCheckResult(
        responsibility_is_exactly_andrei_by_table=responsibility_is_exactly_andrei,
        gauge_group_count=gauge_stats.gauge_group_count,
        gauges_row_count=gauge_stats.gauges_row_count,
        gauge_groups_match_gauges=gauge_stats.gauge_groups_match_gauges,
        partial_gauge_pair_count=gauge_stats.partial_gauge_pair_count,
        inconsistent_link_count=gauge_stats.inconsistent_link_count,
        unexpected_noneligible_gauge_pair_count=gauge_stats.unexpected_noneligible_gauge_pair_count,
        inactive_gauge_count=gauge_stats.inactive_gauge_count,
        gauge_serial_set_matches=gauge_stats.gauge_serial_set_matches,
        audit_problems=audit_problems,
        protected_state_fingerprint_matches=protected_state_fingerprint_matches,
        protected_column_stats=protected_column_stats,
    )


def _print_post_check(result: PostCheckResult) -> None:
    print(f"responsibility_is_exactly_andrei_by_table={result.responsibility_is_exactly_andrei_by_table}")
    print(f"gauge_group_count={result.gauge_group_count} gauges_row_count={result.gauges_row_count} "
          f"gauge_groups_match_gauges={result.gauge_groups_match_gauges}")
    print(f"partial_gauge_pair_count={result.partial_gauge_pair_count} "
          f"inconsistent_link_count={result.inconsistent_link_count}")
    print(f"unexpected_noneligible_gauge_pair_count={result.unexpected_noneligible_gauge_pair_count} "
          f"inactive_gauge_count={result.inactive_gauge_count} "
          f"gauge_serial_set_matches={result.gauge_serial_set_matches}")
    print(f"audit_problems={result.audit_problems}")
    print(f"protected_state_fingerprint_matches={result.protected_state_fingerprint_matches}")
    for s in result.protected_column_stats:
        print(f"{s.table_name}.{s.column_name}: non_null={s.non_null_count} null={s.null_count}")
    print(f"POST_CHECK_OK: {result.ok}")


def run_post_check(engine, expected_protected_state_fingerprint: str) -> bool:
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        db.execute(text("BEGIN TRANSACTION READ ONLY;"))
        ro = db.execute(text("SHOW transaction_read_only;")).scalar()
        print(f"transaction_read_only: {ro}")
        if ro != "on":
            print("STOP: transaction_read_only is not 'on' - aborting before checks.")
            return False
        result = run_post_check_logic(db, expected_protected_state_fingerprint)
        _print_post_check(result)
        return result.ok
    except Exception as e:
        print(f"POST_CHECK_FAILED: {_safe_failure_message(e)}", file=sys.stderr)
        return False
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()


# --- dry-run: same plan as R2b, plus both fingerprints --------------------------------

def run_dry_run(engine) -> bool:
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        db.execute(text("BEGIN TRANSACTION READ ONLY;"))
        ro = db.execute(text("SHOW transaction_read_only;")).scalar()
        print(f"transaction_read_only: {ro}")
        if ro != "on":
            print("STOP: transaction_read_only is not 'on' - aborting before planning.")
            return False
        result = run_plan(db, settings.environment)
        _print_r2b_plan(result)

        ok = result.ok
        preexisting = None
        if result.target.ok:
            preexisting = _check_no_preexisting_r2c_audit_events(db)
            print(f"preexisting_r2c_audit_event_count={preexisting} (must be 0)")
            if preexisting:
                ok = False

            # Current vs. planned vs. expected-after-apply audit_events totals, printed
            # separately so a re-run after further staging activity is easy to compare
            # against an earlier dry-run's numbers.
            planned_total = (
                result.planned_audit_events.legacy_responsibility_assigned
                + result.planned_audit_events.legacy_gauge_created
                + result.planned_audit_events.legacy_gauge_linked
            )
            print(f"current_audit_events_total={result.audit_events_control_count}")
            print(f"planned_r2c_audit_events_total={planned_total}")
            print(
                "expected_audit_events_total_after_apply="
                f"{result.audit_events_control_count + planned_total} (if no further changes occur)"
            )

        # Fingerprints are only meaningful - and only printed - for a plan an --apply
        # could actually be run against: PLAN_OK must be True AND there must be zero
        # preexisting R2c-action audit events. Printing them for an unusable plan would
        # invite pairing a stale/inapplicable --expected-*-fingerprint with --apply -
        # apply_backfill() would still catch the mismatch under its own fresh
        # verification, but this is refused here, earlier and more clearly.
        if ok and preexisting == 0:
            plan_fingerprint, protected_state_fingerprint, _ = _compute_both_fingerprints(db)
            print(f"PLAN_FINGERPRINT: {plan_fingerprint}")
            print(f"PROTECTED_STATE_FINGERPRINT: {protected_state_fingerprint}")
        else:
            print(
                "FINGERPRINTS_NOT_COMPUTED: the plan is not usable for --apply (PLAN_OK is "
                "False and/or preexisting R2c audit events were found) - no "
                "PLAN_FINGERPRINT/PROTECTED_STATE_FINGERPRINT printed."
            )
        return ok
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
    """Same discipline as R2b's dry-run: explicit read-only transaction, checked before
    ever opening the write session below. Does not need to print or check the
    fingerprints itself - apply_backfill() re-verifies everything, including both
    fingerprints, fresh from inside the locked write transaction."""
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        db.execute(text("BEGIN TRANSACTION READ ONLY;"))
        ro = db.execute(text("SHOW transaction_read_only;")).scalar()
        print(f"transaction_read_only: {ro}")
        if ro != "on":
            print("STOP: transaction_read_only is not 'on' - aborting before target checks.")
            return False
        result = run_plan(db, settings.environment)
        _print_r2b_plan(result)
        if not result.ok:
            return False
        preexisting = _check_no_preexisting_r2c_audit_events(db)
        print(f"preexisting_r2c_audit_event_count={preexisting} (must be 0)")
        return preexisting == 0
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Perform the backfill. Default is a read-only dry-run.")
    mode.add_argument("--post-check", action="store_true", help="Read-only: verify the result of a completed apply.")
    parser.add_argument(
        "--expected-plan-fingerprint", type=_fingerprint_arg_type, default=None,
        help="Required with --apply; must exactly match the PLAN_FINGERPRINT printed by a fresh dry-run.",
    )
    parser.add_argument(
        "--expected-protected-state-fingerprint", type=_fingerprint_arg_type, default=None,
        help="Required with --apply and with --post-check; must exactly match PROTECTED_STATE_FINGERPRINT.",
    )
    args = parser.parse_args()

    if args.apply and not args.expected_plan_fingerprint:
        parser.error("--apply requires --expected-plan-fingerprint")
    if args.apply and not args.expected_protected_state_fingerprint:
        parser.error("--apply requires --expected-protected-state-fingerprint")
    if args.expected_plan_fingerprint and not args.apply:
        parser.error("--expected-plan-fingerprint is only valid together with --apply")
    if args.post_check and not args.expected_protected_state_fingerprint:
        parser.error("--post-check requires --expected-protected-state-fingerprint")
    if args.expected_protected_state_fingerprint and not (args.apply or args.post_check):
        parser.error("--expected-protected-state-fingerprint is only valid together with --apply or --post-check")

    try:
        engine = create_engine(settings.database_url)
    except Exception as e:
        print(f"ENGINE_SETUP_FAILED: {_safe_failure_message(e)}", file=sys.stderr)
        return 1

    if args.post_check:
        ok = run_post_check(engine, args.expected_protected_state_fingerprint)
        return 0 if ok else 1

    if not args.apply:
        ok = run_dry_run(engine)
        return 0 if ok else 1

    # --apply path: verify the target+plan before touching anything.
    if not run_pre_apply_check(engine):
        print("REFUSING: target/plan verification failed - no changes made.", file=sys.stderr)
        return 1

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        result = run_apply(
            db, settings.environment,
            args.expected_plan_fingerprint, args.expected_protected_state_fingerprint,
        )
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
    s = result.summary
    print(
        f"APPLY_OK: responsibility_assigned={s.responsibility_assigned_by_table} "
        f"gauges_created={s.gauges_created} revisions_linked={s.revisions_linked} "
        f"audit_events_added={s.audit_events_added}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
