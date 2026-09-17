"""Regression guard for migrations/versions/2327325e8143_repair_pre_r2a_schema_drift.py.

The migration file is imported directly via importlib (its filename starts with a hex
digit, so it cannot be a normal dotted import). Its guard functions are exercised here
against a controlled FakeConn plus monkeypatched _column_info()/_index_info() - never
against a real database - so every accept/reject decision is tested as pure logic. The
actual DDL execution and real pg_catalog shapes (HASH access method, INCLUDE columns,
invalid/not-ready indexes, etc.) are covered separately against a throwaway PostgreSQL
instance, since SQLite has no pg_catalog to construct these shapes against.
"""
import importlib.util
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

_MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "migrations", "versions",
    "2327325e8143_repair_pre_r2a_schema_drift.py",
)
_spec = importlib.util.spec_from_file_location("r2_schema_repair_migration", _MIGRATION_PATH)
repair = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repair)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.plan_r2_legacy_backfill import EXPECTED_ALEMBIC_HEAD  # noqa: E402


class _FakeResult:
    def __init__(self, scalar_return):
        self._scalar_return = scalar_return

    def scalar(self):
        return self._scalar_return

    def fetchone(self):
        return None


class FakeConn:
    """Minimal stand-in for a SQLAlchemy Connection: records every execute() call
    (statement text + params) so a test can assert exactly what DDL, if any, was
    attempted. `scalar_return` controls what a follow-up query (e.g. the duplicate-count
    check in _fix_verification_code_unique_index) reports back."""

    def __init__(self, scalar_return=None):
        self.executed = []
        self._scalar_return = scalar_return

    def execute(self, clause, params=None):
        self.executed.append((str(clause), params))
        return _FakeResult(self._scalar_return)


def _index_info_factory(**overrides):
    defaults = dict(
        table="t", is_unique=False, access_method="btree", key_column_count=1,
        total_column_count=1, has_expression=False, predicate=None,
        is_valid=True, is_ready=True, single_column="c",
        indexdef="CREATE INDEX name ON public.t USING btree (c)",
    )
    defaults.update(overrides)
    return repair.IndexInfo(**defaults)


# --- _fix_widen_not_null_varchar(): type + length + nullability + default ----------

def test_widen_varchar_rejects_unexpected_default_at_old_length(monkeypatch):
    monkeypatch.setattr(repair, "_column_info", lambda conn, t, c: ("character varying", 64, "NO", "'weird'::character varying"))
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_widen_not_null_varchar(conn, "t", "c", old_length=64, new_length=128)
    assert conn.executed == []


def test_widen_varchar_rejects_unexpected_default_at_target_length(monkeypatch):
    """Explicitly required: an unexpected default at the ALREADY-TARGET length must
    also be refused, not treated as "close enough since the length is already right"."""
    monkeypatch.setattr(repair, "_column_info", lambda conn, t, c: ("character varying", 128, "NO", "'weird'::character varying"))
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_widen_not_null_varchar(conn, "t", "c", old_length=64, new_length=128)
    assert conn.executed == []


def test_widen_varchar_accepts_old_length_without_default(monkeypatch):
    monkeypatch.setattr(repair, "_column_info", lambda conn, t, c: ("character varying", 64, "NO", None))
    conn = FakeConn()
    repair._fix_widen_not_null_varchar(conn, "t", "c", old_length=64, new_length=128)
    assert len(conn.executed) == 1
    assert "ALTER COLUMN" in conn.executed[0][0]


def test_widen_varchar_noop_at_target_length_without_default(monkeypatch):
    monkeypatch.setattr(repair, "_column_info", lambda conn, t, c: ("character varying", 128, "NO", None))
    conn = FakeConn()
    repair._fix_widen_not_null_varchar(conn, "t", "c", old_length=64, new_length=128)
    assert conn.executed == []


def test_widen_varchar_rejects_wrong_length_entirely(monkeypatch):
    monkeypatch.setattr(repair, "_column_info", lambda conn, t, c: ("character varying", 100, "NO", None))
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_widen_not_null_varchar(conn, "t", "c", old_length=64, new_length=128)
    assert conn.executed == []


# --- _fix_drop_boolean_default(): type + nullability + exact default ---------------

def test_drop_boolean_default_rejects_nullable_column(monkeypatch):
    monkeypatch.setattr(repair, "_column_info", lambda conn, t, c: ("boolean", None, "YES", "false"))
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_drop_boolean_default(conn, "t", "c", expected_old_default="false")
    assert conn.executed == []


def test_drop_boolean_default_rejects_nullable_column_even_without_default(monkeypatch):
    monkeypatch.setattr(repair, "_column_info", lambda conn, t, c: ("boolean", None, "YES", None))
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_drop_boolean_default(conn, "t", "c", expected_old_default="false")
    assert conn.executed == []


def test_drop_boolean_default_rejects_opposite_default(monkeypatch):
    monkeypatch.setattr(repair, "_column_info", lambda conn, t, c: ("boolean", None, "NO", "true"))
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_drop_boolean_default(conn, "t", "c", expected_old_default="false")
    assert conn.executed == []


def test_drop_boolean_default_accepts_matching_old_default(monkeypatch):
    monkeypatch.setattr(repair, "_column_info", lambda conn, t, c: ("boolean", None, "NO", "false"))
    conn = FakeConn()
    repair._fix_drop_boolean_default(conn, "t", "c", expected_old_default="false")
    assert len(conn.executed) == 1
    assert "DROP DEFAULT" in conn.executed[0][0]


def test_drop_boolean_default_noop_when_already_none(monkeypatch):
    monkeypatch.setattr(repair, "_column_info", lambda conn, t, c: ("boolean", None, "NO", None))
    conn = FakeConn()
    repair._fix_drop_boolean_default(conn, "t", "c", expected_old_default="false")
    assert conn.executed == []


# --- index guards: access method, INCLUDE, expression, valid/ready -----------------

def test_create_plain_index_rejects_hash_access_method(monkeypatch):
    info = _index_info_factory(access_method="hash", indexdef="CREATE INDEX name ON public.t USING hash (c)")
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_create_plain_index(conn, "name", "t", "c")
    assert conn.executed == []


def test_create_plain_index_rejects_include_columns(monkeypatch):
    info = _index_info_factory(total_column_count=2)  # key=1, total=2 -> 1 INCLUDE column
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_create_plain_index(conn, "name", "t", "c")
    assert conn.executed == []


def test_create_plain_index_rejects_expression_index(monkeypatch):
    info = _index_info_factory(has_expression=True, single_column=None)
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_create_plain_index(conn, "name", "t", "c")
    assert conn.executed == []


def test_create_plain_index_rejects_invalid_index(monkeypatch):
    info = _index_info_factory(is_valid=False)
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_create_plain_index(conn, "name", "t", "c")
    assert conn.executed == []


def test_create_plain_index_rejects_not_ready_index(monkeypatch):
    info = _index_info_factory(is_ready=False)
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_create_plain_index(conn, "name", "t", "c")
    assert conn.executed == []


def test_create_plain_index_rejects_predicate(monkeypatch):
    info = _index_info_factory(predicate="is_archived = false")
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_create_plain_index(conn, "name", "t", "c")
    assert conn.executed == []


def test_create_plain_index_rejects_wrong_unique_flag(monkeypatch):
    info = _index_info_factory(is_unique=True, indexdef="CREATE UNIQUE INDEX name ON public.t USING btree (c)")
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_create_plain_index(conn, "name", "t", "c")
    assert conn.executed == []


def test_create_plain_index_rejects_indexdef_mismatch_even_if_structured_fields_match(monkeypatch):
    """Belt-and-suspenders: even if every structured pg_index field matches, a
    normalized pg_get_indexdef() mismatch alone must still refuse."""
    info = _index_info_factory(indexdef="CREATE INDEX name ON public.other_table USING btree (c)")
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_create_plain_index(conn, "name", "t", "c")
    assert conn.executed == []


def test_create_plain_index_noop_when_already_exact(monkeypatch):
    info = _index_info_factory()
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    repair._fix_create_plain_index(conn, "name", "t", "c")
    assert conn.executed == []


def test_create_plain_index_creates_when_absent(monkeypatch):
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: None)
    conn = FakeConn()
    repair._fix_create_plain_index(conn, "name", "t", "c")
    assert len(conn.executed) == 1
    assert "CREATE INDEX" in conn.executed[0][0]


def test_drop_exact_index_noop_when_already_absent(monkeypatch):
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: None)
    conn = FakeConn()
    repair._fix_drop_exact_index(conn, "name", "t", "c")
    assert conn.executed == []


def test_drop_exact_index_rejects_unrecognized_shape(monkeypatch):
    info = _index_info_factory(access_method="hash", indexdef="CREATE INDEX name ON public.t USING hash (c)")
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_drop_exact_index(conn, "name", "t", "c")
    assert conn.executed == []


def test_drop_exact_index_drops_when_exact_match(monkeypatch):
    info = _index_info_factory()
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    repair._fix_drop_exact_index(conn, "name", "t", "c")
    assert len(conn.executed) == 1
    assert "DROP INDEX" in conn.executed[0][0]


# --- _fix_verification_code_unique_index(): wrong access method must still refuse --

def test_verification_code_unique_rejects_wrong_access_method(monkeypatch):
    info = _index_info_factory(
        table="pressure_test_records", single_column="verification_code", is_unique=False,
        access_method="hash",
        indexdef="CREATE INDEX ix_pressure_test_records_verification_code ON public.pressure_test_records USING hash (verification_code)",
    )
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_verification_code_unique_index(conn)
    assert conn.executed == []


def test_verification_code_unique_noop_when_already_unique(monkeypatch):
    info = _index_info_factory(
        table="pressure_test_records", single_column="verification_code", is_unique=True,
        indexdef="CREATE UNIQUE INDEX ix_pressure_test_records_verification_code ON public.pressure_test_records USING btree (verification_code)",
    )
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn()
    repair._fix_verification_code_unique_index(conn)
    assert conn.executed == []


def test_verification_code_unique_refuses_on_duplicates(monkeypatch):
    info = _index_info_factory(
        table="pressure_test_records", single_column="verification_code", is_unique=False,
        indexdef="CREATE INDEX ix_pressure_test_records_verification_code ON public.pressure_test_records USING btree (verification_code)",
    )
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn(scalar_return=1)  # simulates one duplicate group found
    with pytest.raises(repair.SchemaDriftGuardError):
        repair._fix_verification_code_unique_index(conn)
    # the duplicate-count SELECT itself is allowed to run (it is read-only), but no DDL:
    assert not any("DROP INDEX" in stmt or "CREATE" in stmt for stmt, _ in conn.executed)


def test_verification_code_unique_converts_when_no_duplicates(monkeypatch):
    info = _index_info_factory(
        table="pressure_test_records", single_column="verification_code", is_unique=False,
        indexdef="CREATE INDEX ix_pressure_test_records_verification_code ON public.pressure_test_records USING btree (verification_code)",
    )
    monkeypatch.setattr(repair, "_index_info", lambda conn, name: info)
    conn = FakeConn(scalar_return=0)
    repair._fix_verification_code_unique_index(conn)
    ddl_statements = [stmt for stmt, _ in conn.executed if "DROP INDEX" in stmt or "CREATE UNIQUE INDEX" in stmt]
    assert len(ddl_statements) == 2


# --- R2b planner head must match this migration's own revision --------------------

def test_expected_alembic_head_matches_new_revision():
    assert EXPECTED_ALEMBIC_HEAD == repair.revision


# --- downgrade() is a genuine, unconditional no-op ---------------------------------

def test_downgrade_never_touches_the_database(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("downgrade() must never call op.get_bind() or issue any DDL")

    monkeypatch.setattr(repair.op, "get_bind", _boom)
    repair.downgrade()  # must return normally without ever calling get_bind()
