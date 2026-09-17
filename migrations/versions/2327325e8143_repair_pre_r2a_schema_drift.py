"""Repair pre-existing schema drift between the Alembic migration chain, the ORM
models, and live staging - discovered during the R2-schema-repair audit.

Revision ID: 2327325e8143
Revises: addffa66a1d8
Create Date: 2026-09-17 12:00:00.000000

Every object this migration touches predates R2a entirely (it all traces back to
a83e76f92c10_pipecloud_and_composite_ptr.py) and was found only because a fresh
`alembic upgrade head` no longer matches what live staging - and the current ORM
models - actually have. None of it is new schema; this migration reconciles the
migration chain with a state that already exists on live.

Defensive by construction: every single operation below first inspects
pg_catalog/information_schema for the object it is about to touch, and only proceeds
down one of exactly two safe paths:
  - the object is missing / in the exact old-drift shape this migration expects -> fix it.
  - the object already has the exact target shape -> no-op.
Any THIRD shape - anything this migration does not specifically recognize - raises
SchemaDriftGuardError and aborts the entire migration before any DDL runs against that
object. Postgres DDL is transactional, and Alembic already wraps this whole upgrade() in
one transaction, so a raised exception here cleanly rolls back every earlier successful
fix in the same run too - there is no partially-repaired intermediate state (verified
empirically: an induced failure after several successful fixes rolls all of them back).

"Exact shape" for a column always means all four of type, length, nullability, AND
default agree with one of the two recognized states - a column that matches on
type/length/nullability but carries an unexpected default is treated as a third,
unrecognized shape, not as "close enough".

"Exact shape" for an index always means: public schema, btree access method, exactly
one key column (no INCLUDE columns), no expression, no partial predicate (except where
a predicate is itself part of the target definition - none of the indexes this
migration touches have one), indisvalid, indisready, the exact table/column, and the
exact unique/non-unique flag - cross-checked against a normalized pg_get_indexdef()
string as a second, independent confirmation. An index with the right name and column
but the wrong access method, or with INCLUDE columns, or not yet valid/ready, is a third
shape and is refused exactly like a wrong column name would be.

This migration never reads or overwrites the *value* of an existing actor_name or
updated_at - both may carry real historical audit/business data that predates this
Alembic revision entirely. The one exception, backfilling updated_at when the column is
missing, only ever copies from created_at (itself required to be a real, NOT NULL
timestamp already on that same row) - never a literal now().

downgrade() is an intentional, permanent no-op - see its own docstring.
"""
from typing import Optional, Sequence, Tuple, Union

from alembic import op
from sqlalchemy import text


revision: str = "2327325e8143"
down_revision: Union[str, None] = "addffa66a1d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class SchemaDriftGuardError(RuntimeError):
    """Raised when pg_catalog/information_schema shows a column or index in a shape
    this migration does not recognize as either the known pre-existing drift state or
    the already-correct target state. Message text is always safe to print - it never
    includes row content, only schema metadata (table/column/index names, types,
    lengths, counts)."""


# --- introspection helpers, read-only ------------------------------------------------

def _column_info(conn, table: str, column: str) -> Optional[Tuple[str, Optional[int], str, Optional[str]]]:
    """Returns (data_type, character_maximum_length, is_nullable, column_default), or
    None if the column does not exist."""
    row = conn.execute(
        text("""
            SELECT data_type, character_maximum_length, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=:t AND column_name=:c;
        """),
        {"t": table, "c": column},
    ).fetchone()
    return tuple(row) if row else None


class IndexInfo:
    """Full shape of a single-key-column index, or as much of it as could be
    determined. `single_column` and `indexdef` are only populated when the index is
    unambiguously a plain single-key-column index with no expression - callers must
    check `key_column_count`/`has_expression` before trusting `single_column`."""

    def __init__(self, table, is_unique, access_method, key_column_count, total_column_count,
                 has_expression, predicate, is_valid, is_ready, single_column, indexdef):
        self.table = table
        self.is_unique = is_unique
        self.access_method = access_method
        self.key_column_count = key_column_count
        self.total_column_count = total_column_count
        self.has_expression = has_expression
        self.predicate = predicate
        self.is_valid = is_valid
        self.is_ready = is_ready
        self.single_column = single_column
        self.indexdef = indexdef

    def __repr__(self):
        return (
            f"IndexInfo(table={self.table!r}, is_unique={self.is_unique}, "
            f"access_method={self.access_method!r}, key_column_count={self.key_column_count}, "
            f"total_column_count={self.total_column_count}, has_expression={self.has_expression}, "
            f"predicate={self.predicate!r}, is_valid={self.is_valid}, is_ready={self.is_ready}, "
            f"single_column={self.single_column!r})"
        )


def _index_info(conn, index_name: str) -> Optional[IndexInfo]:
    """Read-only, full-shape introspection of a single index by name, scoped to the
    public schema. Returns None if no such index exists there."""
    row = conn.execute(
        text("""
            SELECT tbl.relname, ix.indisunique, am.amname, ix.indnkeyatts, ix.indnatts,
                   (ix.indexprs IS NOT NULL) AS has_expression,
                   pg_get_expr(ix.indpred, ix.indrelid) AS predicate,
                   ix.indisvalid, ix.indisready, pg_get_indexdef(i.oid) AS indexdef
            FROM pg_index ix
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_class tbl ON tbl.oid = ix.indrelid
            JOIN pg_am am ON am.oid = i.relam
            WHERE i.relname = :name AND tbl.relnamespace = 'public'::regnamespace;
        """),
        {"name": index_name},
    ).fetchone()
    if row is None:
        return None
    (table, is_unique, access_method, key_column_count, total_column_count,
     has_expression, predicate, is_valid, is_ready, indexdef) = row

    single_column = None
    if key_column_count == 1 and total_column_count == 1 and not has_expression:
        single_column = conn.execute(
            text("""
                SELECT a.attname
                FROM pg_index ix
                JOIN pg_class tbl ON tbl.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_attribute a ON a.attrelid = tbl.oid AND a.attnum = ix.indkey[0]
                WHERE i.relname = :name AND tbl.relnamespace = 'public'::regnamespace;
            """),
            {"name": index_name},
        ).scalar()

    return IndexInfo(
        table=table, is_unique=bool(is_unique), access_method=access_method,
        key_column_count=key_column_count, total_column_count=total_column_count,
        has_expression=bool(has_expression), predicate=predicate,
        is_valid=bool(is_valid), is_ready=bool(is_ready),
        single_column=single_column, indexdef=indexdef,
    )


def _canonical_indexdef(index_name: str, table: str, column: str, unique: bool) -> str:
    """The exact string Postgres's own pg_get_indexdef() produces for a plain
    single-column btree index with no predicate - used as a second, independent
    confirmation alongside the structured pg_index checks above."""
    kind = "UNIQUE INDEX" if unique else "INDEX"
    return f'CREATE {kind} {index_name} ON public.{table} USING btree ({column})'


def _is_exact_plain_index(info: Optional[IndexInfo], index_name: str, table: str, column: str, unique: bool) -> bool:
    if info is None:
        return False
    return (
        info.table == table
        and info.access_method == "btree"
        and info.key_column_count == 1
        and info.total_column_count == 1
        and not info.has_expression
        and info.predicate is None
        and info.is_valid
        and info.is_ready
        and info.single_column == column
        and info.is_unique == unique
        and info.indexdef == _canonical_indexdef(index_name, table, column, unique)
    )


# --- per-object fixes, each independently guarded ------------------------------------

def _fix_add_nullable_varchar_column(conn, table: str, column: str, length: int) -> None:
    info = _column_info(conn, table, column)
    if info is None:
        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" VARCHAR({length});'))
        return
    data_type, char_len, is_nullable, default = info
    if data_type == "character varying" and char_len == length and is_nullable == "YES" and default is None:
        return  # already the target shape
    raise SchemaDriftGuardError(
        f"Refusing to add {table}.{column}: a column with this name already exists in an "
        f"unrecognized shape (type={data_type}, length={char_len}, nullable={is_nullable}, "
        f"default={default!r})."
    )


def _fix_widen_not_null_varchar(conn, table: str, column: str, old_length: int, new_length: int) -> None:
    """Exact shape means type + length + nullability + default all agree with one of the
    two recognized states (old-drift width or target width) - a column that is
    otherwise correct but carries any default at all, at either width, is a third,
    unrecognized shape (this column has never had a default in any known state)."""
    info = _column_info(conn, table, column)
    if info is None:
        raise SchemaDriftGuardError(f"Refusing: {table}.{column} is missing entirely (expected it to exist).")
    data_type, char_len, is_nullable, default = info
    if data_type != "character varying" or is_nullable != "NO":
        raise SchemaDriftGuardError(
            f"Refusing to widen {table}.{column}: unrecognized shape "
            f"(type={data_type}, nullable={is_nullable})."
        )
    if default is not None:
        raise SchemaDriftGuardError(
            f"Refusing to widen {table}.{column}: found an unexpected default {default!r} - "
            f"this column has no default in either recognized state."
        )
    if char_len == new_length:
        return  # already the target shape
    if char_len != old_length:
        raise SchemaDriftGuardError(
            f"Refusing to widen {table}.{column}: current length {char_len} is neither the "
            f"known old width ({old_length}) nor the target width ({new_length})."
        )
    conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE VARCHAR({new_length});'))


def _fix_create_plain_index(conn, index_name: str, table: str, column: str) -> None:
    info = _index_info(conn, index_name)
    if info is None:
        conn.execute(text(f'CREATE INDEX "{index_name}" ON "{table}" ("{column}");'))
        return
    if _is_exact_plain_index(info, index_name, table, column, unique=False):
        return  # already the target shape
    raise SchemaDriftGuardError(
        f"Refusing to create index '{index_name}': an index with this name already exists "
        f"with an unrecognized shape ({info!r})."
    )


def _fix_drop_exact_index(conn, index_name: str, table: str, column: str) -> None:
    """Only drops the index if it matches the exact known-drift shape this migration is
    authorized to remove - never drops an index just because the name matches."""
    info = _index_info(conn, index_name)
    if info is None:
        return  # already absent - no-op
    if _is_exact_plain_index(info, index_name, table, column, unique=False):
        conn.execute(text(f'DROP INDEX "{index_name}";'))
        return
    raise SchemaDriftGuardError(
        f"Refusing to drop index '{index_name}': found an unrecognized shape ({info!r}) - "
        f"not the specific known-drift index this migration is authorized to remove."
    )


def _fix_drop_boolean_default(conn, table: str, column: str, expected_old_default: str) -> None:
    """expected_old_default is the exact single literal ('true' or 'false') that
    a83e76f92c10's server_default='0'/'1' normalizes to for this specific column - not
    an arbitrary boolean. A default that happens to be a boolean literal but is not THIS
    column's own known old value (e.g. 'true' found where 'false' was expected) is a
    third, unrecognized shape and must still abort, not be treated as interchangeable.
    A column that is nullable is also a third shape - every column this migration
    touches is NOT NULL in both the old-drift and the target state, so nullable=YES can
    never be either recognized state."""
    info = _column_info(conn, table, column)
    if info is None:
        raise SchemaDriftGuardError(f"Refusing: {table}.{column} is missing entirely (expected it to exist).")
    data_type, char_len, is_nullable, default = info
    if data_type != "boolean":
        raise SchemaDriftGuardError(f"Refusing: {table}.{column} is not boolean (type={data_type}).")
    if is_nullable != "NO":
        raise SchemaDriftGuardError(
            f"Refusing: {table}.{column} is nullable ({is_nullable}) - both recognized "
            f"states for this column are NOT NULL."
        )
    if default is None:
        return  # already the target shape
    normalized = default.strip().lower()
    if normalized == expected_old_default:
        conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP DEFAULT;'))
        return
    raise SchemaDriftGuardError(
        f"Refusing to drop default on {table}.{column}: found an unrecognized default "
        f"{default!r}, not a recognized old-drift value."
    )


def _fix_verification_code_unique_index(conn) -> None:
    index_name = "ix_pressure_test_records_verification_code"
    table = "pressure_test_records"
    column = "verification_code"

    info = _index_info(conn, index_name)
    if info is None:
        raise SchemaDriftGuardError(f"Refusing: index '{index_name}' is missing entirely (expected it to exist).")

    # Check every shape property except uniqueness itself first - uniqueness is the
    # ONE property allowed to differ between the two recognized states here.
    non_uniqueness_shape_ok = (
        info.table == table
        and info.access_method == "btree"
        and info.key_column_count == 1
        and info.total_column_count == 1
        and not info.has_expression
        and info.predicate is None
        and info.is_valid
        and info.is_ready
        and info.single_column == column
    )
    if not non_uniqueness_shape_ok:
        raise SchemaDriftGuardError(f"Refusing to touch '{index_name}': found an unrecognized shape ({info!r}).")

    if info.is_unique:
        if info.indexdef != _canonical_indexdef(index_name, table, column, unique=True):
            raise SchemaDriftGuardError(f"Refusing to touch '{index_name}': found an unrecognized shape ({info!r}).")
        return  # already the target shape

    if info.indexdef != _canonical_indexdef(index_name, table, column, unique=False):
        raise SchemaDriftGuardError(f"Refusing to touch '{index_name}': found an unrecognized shape ({info!r}).")

    duplicate_group_count = conn.execute(text(f"""
        SELECT count(*) FROM (
            SELECT "{column}" FROM "{table}"
            WHERE "{column}" IS NOT NULL
            GROUP BY "{column}" HAVING count(*) > 1
        ) x;
    """)).scalar()
    if duplicate_group_count:
        raise SchemaDriftGuardError(
            f"Refusing to make '{index_name}' UNIQUE: {duplicate_group_count} distinct "
            f"non-NULL {table}.{column} value(s) are duplicated. Values are never modified "
            f"by this migration - resolve the duplicates first, then re-run."
        )

    conn.execute(text(f'DROP INDEX "{index_name}";'))
    conn.execute(text(f'CREATE UNIQUE INDEX "{index_name}" ON "{table}" ("{column}");'))


def _fix_pressure_test_record_logs_updated_at(conn) -> None:
    table = "pressure_test_record_logs"

    info = _column_info(conn, table, "updated_at")
    if info is not None:
        data_type, char_len, is_nullable, default = info
        if data_type == "timestamp with time zone" and is_nullable == "NO" and default is None:
            return  # already the target shape - existing values are never touched
        raise SchemaDriftGuardError(
            f"Refusing: {table}.updated_at already exists in an unrecognized shape "
            f"(type={data_type}, nullable={is_nullable}, default={default!r})."
        )

    # Column missing - the known old-drift state. Only proceed if created_at on the
    # same table is a genuinely safe historical source: NOT NULL and already a
    # timestamptz, so every row has a real, non-fabricated value to copy from.
    created_at_info = _column_info(conn, table, "created_at")
    if created_at_info is None:
        raise SchemaDriftGuardError(f"Refusing: {table}.created_at is missing - no safe historical source for updated_at.")
    data_type, char_len, is_nullable, default = created_at_info
    if data_type != "timestamp with time zone" or is_nullable != "NO":
        raise SchemaDriftGuardError(
            f"Refusing: {table}.created_at is not a NOT NULL timestamptz "
            f"(type={data_type}, nullable={is_nullable}) - not a safe historical source for updated_at."
        )

    conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE;'))
    conn.execute(text(f'UPDATE "{table}" SET updated_at = created_at;'))

    remaining_null = conn.execute(text(f'SELECT count(*) FROM "{table}" WHERE updated_at IS NULL;')).scalar()
    if remaining_null:
        raise SchemaDriftGuardError(
            f"Refusing: {remaining_null} row(s) in {table} still have NULL updated_at after "
            f"backfilling from created_at - refusing to silently substitute the current time."
        )

    conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN updated_at SET NOT NULL;'))


# --- upgrade / downgrade --------------------------------------------------------------

def upgrade() -> None:
    conn = op.get_bind()

    _fix_add_nullable_varchar_column(conn, "audit_events", "actor_name", 128)

    _fix_widen_not_null_varchar(conn, "pressure_test_record_items", "pipe_number", old_length=64, new_length=128)
    _fix_widen_not_null_varchar(conn, "pressure_test_record_items", "result", old_length=16, new_length=32)

    _fix_create_plain_index(conn, "ix_pressure_test_record_items_record_log_id", "pressure_test_record_items", "record_log_id")
    _fix_create_plain_index(conn, "ix_pressure_test_record_log_artifacts_artifact_id", "pressure_test_record_log_artifacts", "artifact_id")
    _fix_create_plain_index(conn, "ix_pressure_test_record_logs_test_revision_id", "pressure_test_record_logs", "test_revision_id")

    _fix_pressure_test_record_logs_updated_at(conn)

    _fix_verification_code_unique_index(conn)

    _fix_drop_exact_index(conn, "ix_pressure_test_records_is_archived", "pressure_test_records", "is_archived")

    # expected_old_default is the exact literal a83e76f92c10's server_default='0'/'1'
    # normalizes to for THIS column - not an arbitrary boolean (see the function's own
    # docstring for why 'true' and 'false' are never treated as interchangeable here).
    _fix_drop_boolean_default(conn, "pressure_tests", "pipecloud_added", expected_old_default="false")
    _fix_drop_boolean_default(conn, "pressure_tests", "is_archived", expected_old_default="false")
    _fix_drop_boolean_default(conn, "pressure_test_records", "is_archived", expected_old_default="false")
    _fix_drop_boolean_default(conn, "pressure_test_record_logs", "include_measurement_table", expected_old_default="true")
    _fix_drop_boolean_default(conn, "pressure_test_record_log_artifacts", "is_included_in_pdf", expected_old_default="true")


def downgrade() -> None:
    """Intentional, permanent no-op.

    Every object this migration touches either carries real historical data that
    predates this Alembic revision (audit_events.actor_name, pressure_test_record_logs.
    updated_at) or corrects a previously-inconsistent schema toward what the ORM and
    live staging already required and the application already depends on (the widened
    VARCHAR lengths, the three missing indexes, the UNIQUE verification_code index, the
    removed no-op server defaults, the removed stray is_archived index). Reversing any
    of it would either destroy real data outright, or reintroduce a schema shape that is
    already known to be wrong and that current values may no longer even satisfy (e.g.
    narrowing pipe_number/result back down could truncate/violate existing rows; making
    verification_code non-unique again would silently permit the duplicates the upgrade
    path explicitly checked for). There is nothing safe to reverse here.
    """
    pass
