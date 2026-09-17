#!/usr/bin/env python3
"""R2b: strictly read-only planner for the R2c legacy-backfill decision (ADR-005 SS13
lineage). Produces a diagnostic report only - it never writes.

There is no --apply mode and no write path anywhere in this script. It opens exactly
one explicit `BEGIN TRANSACTION READ ONLY` per run and always ends in ROLLBACK, even on
success. No INSERT/UPDATE/DELETE statement, no ORM session-mutation call (add, flush,
commit), and no argparse flag to enable one, exist anywhere in this file - see
tests/test_plan_r2_legacy_backfill.py::test_script_source_contains_no_write_path for a
static proof of this that runs on every test invocation.

What it reports (all counts/booleans only - never a UUID, Log No., real gauge serial
number, metadata_json content, password, hash, connection string, or .env value):

  1. Target validity: ARDOR_ENV == "staging", PostgreSQL dialect, current_database() ==
     "ardor_pressure_test", Alembic head == 2327325e8143, exactly one active admin-role
     andrei.sakki. The database-identity checks (dialect, current_database, Alembic
     head) surface only as booleans in every output path - the actual database name or
     connection string is never printed, even when the check fails. All of this runs
     before any R2a-specific table or column is ever queried.
  2. For pressure_tests / planned_test_lists / pressure_test_records: total rows,
     responsible_user_id NULL count, already-andrei count, already-assigned-to-someone-
     else count, and the resulting planned assignment/audit-event count for a future
     R2c apply.
  3. Protected legacy/actor columns (created_by_user_id, updated_by_user_id,
     confirmed_by_user_id, pipecloud_updated_by_user_id, audit_events): control counts
     only - this script never proposes a plan to change any of them.
  4. Legacy metadata_json.wika_nr statistics (missing/blank/nonblank, normalized-group
     count, raw-formatting-conflict count, a breakdown by every distinct status value
     actually present - not hardcoded to draft/complete, since the model allows draft,
     complete, confirmed, and archived - how many revisions could later receive a
     gauge_id + snapshot, how many Gauge rows that would require) - without ever
     printing an actual serial number. Only the status label itself and counts are
     printed, never a Log No.
  5. R2a field state: existing gauges rows, already-filled gauge_id/gauge_serial_snapshot,
     partial (exactly one of the pair set) or inconsistent pairs, already-filled
     responsible_user_id - any of these being non-empty is a stop condition, since R2b
     assumes it is planning against a schema that has not been used yet.
  6. The future R2c audit-event counts this plan implies, broken out by action name:
     legacy_responsibility_assigned (per top-level material row), legacy_gauge_created
     (per new Gauge), legacy_gauge_linked (per revision that would gain a gauge_id).
  7. Two separate, explicit blockers, never silently ignored or auto-filled:
       - finalized-status (complete/confirmed/archived) revisions with no usable legacy
         gauge value to backfill from. Draft is mutable and is never a blocker by
         itself - only a revision the model no longer expects to change qualifies.
       - any revision whose status is not one of draft/complete/confirmed/archived, in
         its own right, regardless of its wika_nr content - this planner cannot
         classify an unrecognized status as either mutable or safely finalized.
     Both are reported as their own counts so the owner can decide what to do with
     those rows.

PLAN_OK is True only if the target is valid AND no stop condition below was triggered.
A false PLAN_OK does not mean the report is incomplete - every section that is safe to
compute (i.e. the target itself is valid) is still computed and printed, so the full
picture is visible even when some sections signal a problem.
"""
import argparse
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from services.api.config import settings
from services.api.models import User

EXPECTED_ARDOR_ENV = "staging"
EXPECTED_DATABASE_NAME = "ardor_pressure_test"
EXPECTED_ALEMBIC_HEAD = "2327325e8143"
ANDREI_USERNAME = "andrei.sakki"
RESPONSIBILITY_TABLES = ("pressure_tests", "planned_test_lists", "pressure_test_records")
KNOWN_STATUSES = ("draft", "complete", "confirmed", "archived")
FINALIZED_STATUSES = ("complete", "confirmed", "archived")  # legacy-frozen, not editable in Draft's sense

# (table, column) pairs that are never proposed for change by this planner - only
# reported as control counts. Each pair either predates R2a (no FK, historical
# authorship/confirmation/edit attribution) or is a new R2a column this planner
# deliberately leaves alone (created_by_user_id/updated_by_user_id are a separate,
# not-yet-decided backfill question from responsible_user_id).
PROTECTED_COLUMNS = (
    ("pressure_tests", "created_by_user_id"),
    ("pressure_tests", "updated_by_user_id"),
    ("pressure_tests", "pipecloud_updated_by_user_id"),
    ("test_revisions", "created_by_user_id"),
    ("test_revisions", "updated_by_user_id"),
    ("pressure_test_records", "created_by_user_id"),
    ("pressure_test_records", "updated_by_user_id"),
    ("pressure_test_records", "confirmed_by_user_id"),
    ("planned_test_lists", "created_by_user_id"),
    ("planned_test_lists", "updated_by_user_id"),
)


def _safe_failure_message(exc: BaseException) -> str:
    """Never surface a raw exception's full text - SQLAlchemy/psycopg2 exceptions often
    embed the failing SQL statement and its bound parameters in str(exc), and a
    malformed settings.database_url itself may embed a password."""
    return f"{type(exc).__name__} (details withheld: may contain SQL text/parameters)"


# --- 1. target validity -------------------------------------------------------------

@dataclass
class TargetCheckResult:
    ardor_env_is_staging: bool
    dialect_is_postgresql: bool
    current_database_is_expected: bool
    alembic_head_is_expected: bool
    andrei_count: int
    andrei_is_active_admin: bool
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def verify_target(db: Session, environment: str) -> TargetCheckResult:
    """Every check here runs before any R2a-table query elsewhere in this script (see
    run_plan(), which returns immediately if this fails). Only booleans are ever
    returned/printed for the database-identity checks below - never the actual
    current_database() name or connection string, which could otherwise leak
    infrastructure details into a report meant to be safe to share."""
    ardor_env_is_staging = environment.strip() == EXPECTED_ARDOR_ENV

    engine = db.get_bind()
    dialect_is_postgresql = engine.dialect.name == "postgresql"

    current_database_is_expected = False
    alembic_head_is_expected = False
    if dialect_is_postgresql:
        current_database_name = db.execute(text("SELECT current_database();")).scalar()
        current_database_is_expected = current_database_name == EXPECTED_DATABASE_NAME

        try:
            current_alembic_head = db.execute(text("SELECT version_num FROM alembic_version;")).scalar()
        except Exception:
            current_alembic_head = None
        alembic_head_is_expected = current_alembic_head == EXPECTED_ALEMBIC_HEAD

    # users.username carries a UNIQUE index, so andrei_count > 1 cannot occur through
    # normal insertion - this check is deliberate defense-in-depth, not a scenario this
    # script's own test suite can construct against the real schema.
    andrei_rows = db.query(User).filter(User.username == ANDREI_USERNAME).all()
    andrei_count = len(andrei_rows)
    andrei_is_active_admin = (
        andrei_count == 1 and andrei_rows[0].is_active and andrei_rows[0].role == "admin"
    )

    problems: List[str] = []
    if not ardor_env_is_staging:
        problems.append(f"ARDOR_ENV is not '{EXPECTED_ARDOR_ENV}'")
    if not dialect_is_postgresql:
        problems.append("database dialect is not PostgreSQL")
    if dialect_is_postgresql and not current_database_is_expected:
        problems.append(f"current_database() is not '{EXPECTED_DATABASE_NAME}'")
    if dialect_is_postgresql and not alembic_head_is_expected:
        problems.append(f"Alembic head is not '{EXPECTED_ALEMBIC_HEAD}'")
    if andrei_count == 0:
        problems.append(f"'{ANDREI_USERNAME}' is missing")
    elif andrei_count > 1:
        problems.append(f"'{ANDREI_USERNAME}' is duplicated ({andrei_count} rows)")
    elif not andrei_is_active_admin:
        problems.append(f"'{ANDREI_USERNAME}' is inactive or not role='admin'")

    return TargetCheckResult(
        ardor_env_is_staging=ardor_env_is_staging,
        dialect_is_postgresql=dialect_is_postgresql,
        current_database_is_expected=current_database_is_expected,
        alembic_head_is_expected=alembic_head_is_expected,
        andrei_count=andrei_count,
        andrei_is_active_admin=andrei_is_active_admin,
        problems=problems,
    )


# --- 2. responsible_user_id backfill plan, per top-level table ----------------------

@dataclass
class ResponsibilityStats:
    table_name: str
    total_rows: int
    responsible_null: int
    responsible_already_andrei: int
    responsible_assigned_to_other: int

    @property
    def planned_assignments(self) -> int:
        return self.responsible_null

    @property
    def planned_audit_events(self) -> int:
        return self.responsible_null


def compute_responsibility_stats(db: Session, table_name: str, andrei_id: str) -> ResponsibilityStats:
    total_rows = db.execute(text(f'SELECT count(*) FROM "{table_name}";')).scalar()
    responsible_null = db.execute(
        text(f'SELECT count(*) FROM "{table_name}" WHERE responsible_user_id IS NULL;')
    ).scalar()
    responsible_already_andrei = db.execute(
        text(f'SELECT count(*) FROM "{table_name}" WHERE responsible_user_id = :andrei_id;'),
        {"andrei_id": andrei_id},
    ).scalar()
    responsible_assigned_to_other = db.execute(
        text(
            f'SELECT count(*) FROM "{table_name}" '
            f'WHERE responsible_user_id IS NOT NULL AND responsible_user_id != :andrei_id;'
        ),
        {"andrei_id": andrei_id},
    ).scalar()
    return ResponsibilityStats(
        table_name=table_name,
        total_rows=total_rows,
        responsible_null=responsible_null,
        responsible_already_andrei=responsible_already_andrei,
        responsible_assigned_to_other=responsible_assigned_to_other,
    )


# --- 3. protected columns: control counts only, no plan ----------------------------

@dataclass
class ProtectedColumnStats:
    table_name: str
    column_name: str
    non_null_count: int
    null_count: int


def compute_protected_column_stats(db: Session, table_name: str, column_name: str) -> ProtectedColumnStats:
    non_null_count = db.execute(
        text(f'SELECT count(*) FROM "{table_name}" WHERE "{column_name}" IS NOT NULL;')
    ).scalar()
    null_count = db.execute(
        text(f'SELECT count(*) FROM "{table_name}" WHERE "{column_name}" IS NULL;')
    ).scalar()
    return ProtectedColumnStats(
        table_name=table_name, column_name=column_name,
        non_null_count=non_null_count, null_count=null_count,
    )


def compute_audit_events_control_count(db: Session) -> int:
    return db.execute(text("SELECT count(*) FROM audit_events;")).scalar()


# --- 4. legacy wika_nr stats, never printing an actual serial ----------------------

@dataclass
class StatusWikaNrBreakdown:
    status: str
    total: int
    nonblank: int

    @property
    def blank_or_missing(self) -> int:
        return self.total - self.nonblank


@dataclass
class WikaNrStats:
    total_revisions: int
    missing_or_null: int
    blank: int
    nonblank: int
    normalized_group_count: int
    formatting_conflict_group_count: int
    status_breakdown: List[StatusWikaNrBreakdown]
    revisions_eligible_for_gauge_link: int
    gauges_to_create: int


def compute_wika_nr_stats(db: Session) -> WikaNrStats:
    total_revisions = db.execute(text("SELECT count(*) FROM test_revisions;")).scalar()

    nonblank_predicate = (
        "metadata_json::jsonb ? 'wika_nr' AND trim(metadata_json->>'wika_nr') != ''"
    )
    blank_predicate = (
        "metadata_json::jsonb ? 'wika_nr' AND trim(metadata_json->>'wika_nr') = ''"
    )

    nonblank = db.execute(text(f"SELECT count(*) FROM test_revisions WHERE {nonblank_predicate};")).scalar()
    blank = db.execute(text(f"SELECT count(*) FROM test_revisions WHERE {blank_predicate};")).scalar()
    missing_or_null = total_revisions - nonblank - blank

    normalized_group_count = db.execute(text(f"""
        SELECT count(DISTINCT upper(trim(metadata_json->>'wika_nr')))
        FROM test_revisions WHERE {nonblank_predicate};
    """)).scalar()

    formatting_conflict_group_count = db.execute(text(f"""
        SELECT count(*) FROM (
            SELECT upper(trim(metadata_json->>'wika_nr')) AS norm,
                   count(DISTINCT metadata_json->>'wika_nr') AS variants
            FROM test_revisions WHERE {nonblank_predicate}
            GROUP BY upper(trim(metadata_json->>'wika_nr'))
            HAVING count(DISTINCT metadata_json->>'wika_nr') > 1
        ) x;
    """)).scalar()

    # Per-status breakdown, over every distinct status value actually present - not
    # hardcoded to draft/complete, so an unexpected status value shows up here too
    # rather than being silently ignored.
    status_rows = db.execute(text(f"""
        SELECT status, count(*) AS total,
               sum(CASE WHEN {nonblank_predicate} THEN 1 ELSE 0 END) AS nonblank
        FROM test_revisions GROUP BY status ORDER BY status;
    """)).fetchall()
    status_breakdown = [
        StatusWikaNrBreakdown(status=row[0], total=row[1], nonblank=int(row[2] or 0))
        for row in status_rows
    ]

    return WikaNrStats(
        total_revisions=total_revisions,
        missing_or_null=missing_or_null,
        blank=blank,
        nonblank=nonblank,
        normalized_group_count=normalized_group_count,
        formatting_conflict_group_count=formatting_conflict_group_count,
        status_breakdown=status_breakdown,
        revisions_eligible_for_gauge_link=nonblank,
        gauges_to_create=normalized_group_count,
    )


# --- 5. R2a field state: must be untouched so far -----------------------------------

@dataclass
class R2aFieldStats:
    gauges_row_count: int
    gauge_id_filled_count: int
    gauge_serial_snapshot_filled_count: int
    partial_gauge_pair_count: int
    responsible_already_filled_by_table: Dict[str, int]


def compute_r2a_field_stats(db: Session, responsibility_stats: List[ResponsibilityStats]) -> R2aFieldStats:
    gauges_row_count = db.execute(text("SELECT count(*) FROM gauges;")).scalar()
    gauge_id_filled = db.execute(text("SELECT count(*) FROM test_revisions WHERE gauge_id IS NOT NULL;")).scalar()
    snapshot_filled = db.execute(
        text("SELECT count(*) FROM test_revisions WHERE gauge_serial_snapshot IS NOT NULL;")
    ).scalar()
    partial_pair = db.execute(text("""
        SELECT count(*) FROM test_revisions
        WHERE (gauge_id IS NOT NULL AND gauge_serial_snapshot IS NULL)
           OR (gauge_id IS NULL AND gauge_serial_snapshot IS NOT NULL);
    """)).scalar()

    responsible_already_filled = {
        s.table_name: s.responsible_already_andrei + s.responsible_assigned_to_other
        for s in responsibility_stats
    }

    return R2aFieldStats(
        gauges_row_count=gauges_row_count,
        gauge_id_filled_count=gauge_id_filled,
        gauge_serial_snapshot_filled_count=snapshot_filled,
        partial_gauge_pair_count=partial_pair,
        responsible_already_filled_by_table=responsible_already_filled,
    )


# --- 6. planned future audit events, by action --------------------------------------

@dataclass
class PlannedAuditEventCounts:
    legacy_responsibility_assigned: int
    legacy_gauge_created: int
    legacy_gauge_linked: int


def compute_planned_audit_event_counts(
    responsibility_stats: List[ResponsibilityStats], wika_nr_stats: WikaNrStats
) -> PlannedAuditEventCounts:
    return PlannedAuditEventCounts(
        legacy_responsibility_assigned=sum(s.planned_audit_events for s in responsibility_stats),
        legacy_gauge_created=wika_nr_stats.gauges_to_create,
        legacy_gauge_linked=wika_nr_stats.revisions_eligible_for_gauge_link,
    )


# --- 7. finalized-status-without-legacy-gauge blocker: never auto-filled ------------
#     Draft is mutable and is never a blocker by itself. complete/confirmed/archived are
#     legacy-frozen: any such revision with no usable wika_nr value cannot be backfilled
#     and is reported as a blocker for the owner to decide on. A status outside the four
#     known values is its own separate blocker, regardless of its wika_nr content,
#     because this planner cannot classify it as either mutable or safely finalized.

@dataclass
class FinalizedWithoutGaugeBlocker:
    finalized_revisions_total: int
    finalized_revisions_without_legacy_gauge: int
    without_legacy_gauge_by_status: Dict[str, int]


def compute_finalized_without_gauge_blocker(wika_nr_stats: WikaNrStats) -> FinalizedWithoutGaugeBlocker:
    finalized_rows = [r for r in wika_nr_stats.status_breakdown if r.status in FINALIZED_STATUSES]
    return FinalizedWithoutGaugeBlocker(
        finalized_revisions_total=sum(r.total for r in finalized_rows),
        finalized_revisions_without_legacy_gauge=sum(r.blank_or_missing for r in finalized_rows),
        without_legacy_gauge_by_status={r.status: r.blank_or_missing for r in finalized_rows},
    )


@dataclass
class UnknownStatusBlocker:
    unknown_status_revision_count: int
    unknown_statuses: List[str]


def compute_unknown_status_blocker(wika_nr_stats: WikaNrStats) -> UnknownStatusBlocker:
    unknown_rows = [r for r in wika_nr_stats.status_breakdown if r.status not in KNOWN_STATUSES]
    return UnknownStatusBlocker(
        unknown_status_revision_count=sum(r.total for r in unknown_rows),
        unknown_statuses=sorted(r.status for r in unknown_rows),
    )


# --- top-level plan assembly ---------------------------------------------------------

@dataclass
class PlanResult:
    target: TargetCheckResult
    responsibility_stats: Optional[List[ResponsibilityStats]] = None
    protected_column_stats: Optional[List[ProtectedColumnStats]] = None
    audit_events_control_count: Optional[int] = None
    wika_nr_stats: Optional[WikaNrStats] = None
    r2a_field_stats: Optional[R2aFieldStats] = None
    planned_audit_events: Optional[PlannedAuditEventCounts] = None
    finalized_blocker: Optional[FinalizedWithoutGaugeBlocker] = None
    unknown_status_blocker: Optional[UnknownStatusBlocker] = None
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.target.ok and not self.problems


def run_plan(db: Session, environment: str) -> PlanResult:
    """Pure read-only planning logic. Issues only SELECT statements. The caller is
    responsible for the BEGIN TRANSACTION READ ONLY / ROLLBACK wrapper. verify_target()
    - including ARDOR_ENV, dialect, current_database(), and Alembic head - always runs
    first and, on failure, returns immediately without touching any R2a-specific table
    or column below it."""
    target = verify_target(db, environment)
    if not target.ok:
        return PlanResult(target=target)

    andrei = db.query(User).filter(User.username == ANDREI_USERNAME).first()
    andrei_id = andrei.id

    responsibility_stats = [
        compute_responsibility_stats(db, table, andrei_id) for table in RESPONSIBILITY_TABLES
    ]
    protected_column_stats = [
        compute_protected_column_stats(db, table, column) for table, column in PROTECTED_COLUMNS
    ]
    audit_events_control_count = compute_audit_events_control_count(db)
    wika_nr_stats = compute_wika_nr_stats(db)
    r2a_field_stats = compute_r2a_field_stats(db, responsibility_stats)
    planned_audit_events = compute_planned_audit_event_counts(responsibility_stats, wika_nr_stats)
    finalized_blocker = compute_finalized_without_gauge_blocker(wika_nr_stats)
    unknown_status_blocker = compute_unknown_status_blocker(wika_nr_stats)

    problems: List[str] = []
    for s in responsibility_stats:
        # Before the first R2c apply, every row's responsible_user_id must be NULL -
        # not "NULL or already andrei". A row already showing andrei here means either a
        # prior partial apply or an out-of-band write, and R2c's own idempotency guard
        # (refuse whenever gauges is non-empty) does not by itself catch that case, since
        # responsible_user_id and gauges are populated by two different steps of the
        # same apply - so this check has to stand on its own.
        already_set = s.responsible_already_andrei + s.responsible_assigned_to_other
        if already_set > 0:
            problems.append(
                f"{s.table_name}: {already_set} row(s) already have responsible_user_id set "
                f"(already_andrei={s.responsible_already_andrei}, "
                f"assigned_to_other={s.responsible_assigned_to_other}) - before the first R2c "
                f"apply every row's responsible_user_id must be NULL"
            )
    if r2a_field_stats.gauges_row_count > 0:
        problems.append(f"gauges table is not empty ({r2a_field_stats.gauges_row_count} row(s))")
    if r2a_field_stats.gauge_id_filled_count > 0:
        problems.append(f"test_revisions.gauge_id already filled on {r2a_field_stats.gauge_id_filled_count} row(s)")
    if r2a_field_stats.gauge_serial_snapshot_filled_count > 0:
        problems.append(
            f"test_revisions.gauge_serial_snapshot already filled on "
            f"{r2a_field_stats.gauge_serial_snapshot_filled_count} row(s)"
        )
    if r2a_field_stats.partial_gauge_pair_count > 0:
        problems.append(
            f"test_revisions has {r2a_field_stats.partial_gauge_pair_count} row(s) with an "
            f"incomplete gauge_id/gauge_serial_snapshot pair"
        )
    if wika_nr_stats.formatting_conflict_group_count > 0:
        problems.append(
            f"{wika_nr_stats.formatting_conflict_group_count} normalized wika_nr group(s) "
            f"have conflicting raw formatting variants"
        )
    if finalized_blocker.finalized_revisions_without_legacy_gauge > 0:
        problems.append(
            f"BLOCKER: {finalized_blocker.finalized_revisions_without_legacy_gauge} finalized-status "
            f"(complete/confirmed/archived) revision(s) have no usable legacy gauge value - "
            f"not auto-assignable, owner decision required "
            f"(by status: {finalized_blocker.without_legacy_gauge_by_status})"
        )
    if unknown_status_blocker.unknown_status_revision_count > 0:
        problems.append(
            f"BLOCKER: {unknown_status_blocker.unknown_status_revision_count} revision(s) have a "
            f"status outside draft/complete/confirmed/archived "
            f"(statuses: {unknown_status_blocker.unknown_statuses}) - not classifiable, owner decision required"
        )

    return PlanResult(
        target=target,
        responsibility_stats=responsibility_stats,
        protected_column_stats=protected_column_stats,
        audit_events_control_count=audit_events_control_count,
        wika_nr_stats=wika_nr_stats,
        r2a_field_stats=r2a_field_stats,
        planned_audit_events=planned_audit_events,
        finalized_blocker=finalized_blocker,
        unknown_status_blocker=unknown_status_blocker,
        problems=problems,
    )


def _print_plan(result: PlanResult) -> None:
    t = result.target
    print(f"ardor_env_is_staging: {t.ardor_env_is_staging}")
    print(f"dialect_is_postgresql: {t.dialect_is_postgresql}")
    print(f"current_database_is_expected: {t.current_database_is_expected} (expected '{EXPECTED_DATABASE_NAME}')")
    print(f"alembic_head_is_expected: {t.alembic_head_is_expected} (expected '{EXPECTED_ALEMBIC_HEAD}')")
    print(f"andrei_count: {t.andrei_count}")
    print(f"andrei_is_active_admin: {t.andrei_is_active_admin}")
    if not t.ok:
        print("TARGET_PROBLEMS: " + "; ".join(t.problems))
        print(f"PLAN_OK: {result.ok}")
        return

    print()
    print("--- responsibility (responsible_user_id) ---")
    for s in result.responsibility_stats:
        print(
            f"{s.table_name}: total={s.total_rows} null={s.responsible_null} "
            f"already_andrei={s.responsible_already_andrei} "
            f"assigned_to_other={s.responsible_assigned_to_other} "
            f"planned_assignments={s.planned_assignments} planned_audit_events={s.planned_audit_events}"
        )

    print()
    print("--- protected columns (control counts only, no plan) ---")
    for s in result.protected_column_stats:
        print(f"{s.table_name}.{s.column_name}: non_null={s.non_null_count} null={s.null_count}")
    print(f"audit_events total: {result.audit_events_control_count}")

    print()
    print("--- legacy wika_nr (metadata_json) ---")
    w = result.wika_nr_stats
    print(
        f"total_revisions={w.total_revisions} missing_or_null={w.missing_or_null} "
        f"blank={w.blank} nonblank={w.nonblank}"
    )
    print(
        f"normalized_group_count={w.normalized_group_count} "
        f"formatting_conflict_group_count={w.formatting_conflict_group_count}"
    )
    for s in w.status_breakdown:
        mutable = "mutable" if s.status == "draft" else ("finalized" if s.status in FINALIZED_STATUSES else "UNKNOWN")
        print(
            f"status={s.status} ({mutable}): total={s.total} nonblank={s.nonblank} "
            f"blank_or_missing={s.blank_or_missing}"
        )
    print(
        f"revisions_eligible_for_gauge_link={w.revisions_eligible_for_gauge_link} "
        f"gauges_to_create={w.gauges_to_create}"
    )

    print()
    print("--- R2a field state (must be untouched pre-R2c) ---")
    r = result.r2a_field_stats
    print(f"gauges_row_count={r.gauges_row_count}")
    print(
        f"gauge_id_filled_count={r.gauge_id_filled_count} "
        f"gauge_serial_snapshot_filled_count={r.gauge_serial_snapshot_filled_count} "
        f"partial_gauge_pair_count={r.partial_gauge_pair_count}"
    )
    print(f"responsible_already_filled_by_table={r.responsible_already_filled_by_table}")

    print()
    print("--- planned R2c audit events ---")
    p = result.planned_audit_events
    print(
        f"legacy_responsibility_assigned={p.legacy_responsibility_assigned} "
        f"legacy_gauge_created={p.legacy_gauge_created} "
        f"legacy_gauge_linked={p.legacy_gauge_linked}"
    )

    print()
    print("--- finalized-status (complete/confirmed/archived) without legacy gauge blocker ---")
    fb = result.finalized_blocker
    print(
        f"finalized_revisions_total={fb.finalized_revisions_total} "
        f"finalized_revisions_without_legacy_gauge={fb.finalized_revisions_without_legacy_gauge} "
        f"by_status={fb.without_legacy_gauge_by_status}"
    )

    print()
    print("--- unknown-status blocker ---")
    ub = result.unknown_status_blocker
    print(
        f"unknown_status_revision_count={ub.unknown_status_revision_count} "
        f"unknown_statuses={ub.unknown_statuses}"
    )

    print()
    if result.problems:
        print("PROBLEMS: " + "; ".join(result.problems))
    print(f"PLAN_OK: {result.ok}")


def run_dry_plan(engine) -> bool:
    """The only entry point this script has. Opens an explicit read-only transaction,
    runs run_plan(), always rolls back. Never writes under any circumstance."""
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
        _print_plan(result)
        return result.ok
    except Exception as e:
        print(f"PLAN_FAILED: {_safe_failure_message(e)}", file=sys.stderr)
        return False
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()


def main() -> Optional[int]:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # No arguments: this script has exactly one mode, a read-only plan. There is no
    # --apply flag and never will be one in this file - see the module docstring.
    parser.parse_args()

    try:
        engine = create_engine(settings.database_url)
    except Exception as e:
        print(f"ENGINE_SETUP_FAILED: {_safe_failure_message(e)}", file=sys.stderr)
        return 1

    ok = run_dry_plan(engine)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
