"""Regression guard for the R3b-1 additive session schema (UserSession / `sessions`
table, `users.must_change_password`).

Covers only the ORM/model shape - the actual Alembic migration (d3fc3cb2ef8b) is
verified separately against a throwaway PostgreSQL instance (upgrade from the prior
head with pre-existing users seeded -> inspect table/constraints/indexes via \\d ->
compare_metadata() -> upgrade further from an empty DB -> downgrade -> schema-only dump
diff against a DB that never saw this migration), not here - SQLite does not enforce
foreign keys by default and this migration's FK/index shape is exactly what needs that
real-Postgres proof. Same split as tests/test_r2a_data_model.py.

This stage is schema only: no auth behavior, routes, cookie/JWT/CSRF logic, Argon2,
rate limiting, frontend, or desktop code exists yet that reads or writes any of these
new columns - these tests only prove the table/column/constraint/index shape itself.

Isolated by design, same pattern as every other regression test in this repo: a private
in-memory SQLite session, never the process-wide engine.
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

import datetime
import os as _os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.database import Base
from services.api.models import User, UserSession, generate_uuid, utc_now


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
def seeded_user(db_session):
    u = User(username="session_owner", hashed_password="x", role="viewer")
    db_session.add(u)
    db_session.commit()
    return u


HASH64 = "a" * 64
HASH64_B = "b" * 64
HASH64_C = "c" * 64


def _valid_browser_kwargs(user_id, **overrides):
    now = utc_now()
    kwargs = dict(
        user_id=user_id,
        channel="browser",
        token_hash=HASH64,
        previous_token_hash=None,
        csrf_token_hash=HASH64_B,
        expires_at=now + datetime.timedelta(days=30),
    )
    kwargs.update(overrides)
    return kwargs


def _valid_desktop_kwargs(user_id, **overrides):
    now = utc_now()
    kwargs = dict(
        user_id=user_id,
        channel="desktop",
        token_hash=HASH64,
        previous_token_hash=None,
        csrf_token_hash=None,
        expires_at=now + datetime.timedelta(days=30),
    )
    kwargs.update(overrides)
    return kwargs


# --- users.must_change_password: additive, defaults false ---------------------------

def test_new_user_defaults_must_change_password_false(db_session):
    u = User(username="fresh_account", hashed_password="x")
    db_session.add(u)
    db_session.commit()
    assert u.must_change_password is False


# --- UserSession: exact column set ---------------------------------------------------

def test_user_session_table_has_exactly_the_expected_columns():
    columns = {c.name for c in UserSession.__table__.columns}
    assert columns == {
        "id", "user_id", "channel", "token_hash", "previous_token_hash", "csrf_token_hash",
        "created_at", "last_seen_at", "expires_at", "revoked_at", "revoked_reason",
        "device_label", "ip_address", "user_agent",
    }


def test_user_id_foreign_key_has_no_ondelete_cascade():
    """Declared-shape proof (no cascade configured at all, matching every other
    users.id FK in this file); actual enforcement against a real referenced row is a
    Postgres-only concern, since SQLite does not enforce FKs by default - covered in
    the throwaway-Postgres tier."""
    fks = list(UserSession.__table__.c.user_id.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.column.table.name == "users"
    assert fk.column.name == "id"
    assert fk.ondelete is None


def test_token_hash_column_is_not_nullable():
    assert UserSession.__table__.c.token_hash.nullable is False


def test_channel_column_is_not_nullable():
    assert UserSession.__table__.c.channel.nullable is False


# --- valid rows for both channels ----------------------------------------------------

def test_valid_browser_row_inserts_successfully(db_session, seeded_user):
    s = UserSession(**_valid_browser_kwargs(seeded_user.id))
    db_session.add(s)
    db_session.commit()
    assert s.id is not None
    assert s.revoked_at is None
    assert s.revoked_reason is None


def test_valid_desktop_row_inserts_successfully(db_session, seeded_user):
    s = UserSession(**_valid_desktop_kwargs(seeded_user.id))
    db_session.add(s)
    db_session.commit()
    assert s.id is not None


def test_valid_desktop_row_with_previous_token_hash_inserts_successfully(db_session, seeded_user):
    s = UserSession(**_valid_desktop_kwargs(seeded_user.id, previous_token_hash=HASH64_C))
    db_session.add(s)
    db_session.commit()
    assert s.previous_token_hash == HASH64_C


# --- ck_sessions_channel --------------------------------------------------------------

def test_channel_check_rejects_unrecognized_value(db_session, seeded_user):
    s = UserSession(**_valid_desktop_kwargs(seeded_user.id, channel="bogus", csrf_token_hash=None))
    db_session.add(s)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- ck_sessions_csrf_token_hash_by_channel -------------------------------------------

def test_browser_requires_csrf_token_hash(db_session, seeded_user):
    s = UserSession(**_valid_browser_kwargs(seeded_user.id, csrf_token_hash=None))
    db_session.add(s)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_desktop_forbids_csrf_token_hash(db_session, seeded_user):
    s = UserSession(**_valid_desktop_kwargs(seeded_user.id, csrf_token_hash=HASH64_B))
    db_session.add(s)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- ck_sessions_previous_token_hash_desktop_only -------------------------------------

def test_browser_forbids_previous_token_hash(db_session, seeded_user):
    s = UserSession(**_valid_browser_kwargs(seeded_user.id, previous_token_hash=HASH64_C))
    db_session.add(s)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- ck_sessions_revoked_at_reason_together -------------------------------------------

def test_revoked_at_and_reason_both_null_is_valid(db_session, seeded_user):
    s = UserSession(**_valid_browser_kwargs(seeded_user.id))
    db_session.add(s)
    db_session.commit()
    assert s.revoked_at is None and s.revoked_reason is None


def test_revoked_at_and_reason_both_set_is_valid(db_session, seeded_user):
    s = UserSession(**_valid_browser_kwargs(
        seeded_user.id, revoked_at=utc_now(), revoked_reason="logout",
    ))
    db_session.add(s)
    db_session.commit()
    assert s.revoked_at is not None and s.revoked_reason == "logout"


def test_revoked_at_without_reason_is_rejected(db_session, seeded_user):
    s = UserSession(**_valid_browser_kwargs(seeded_user.id, revoked_at=utc_now(), revoked_reason=None))
    db_session.add(s)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_revoked_reason_without_revoked_at_is_rejected(db_session, seeded_user):
    s = UserSession(**_valid_browser_kwargs(seeded_user.id, revoked_at=None, revoked_reason="logout"))
    db_session.add(s)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- hash length checks (64 chars when present) ---------------------------------------

def test_token_hash_wrong_length_is_rejected(db_session, seeded_user):
    s = UserSession(**_valid_desktop_kwargs(seeded_user.id, token_hash="short"))
    db_session.add(s)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_previous_token_hash_wrong_length_is_rejected(db_session, seeded_user):
    s = UserSession(**_valid_desktop_kwargs(seeded_user.id, previous_token_hash="short"))
    db_session.add(s)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_csrf_token_hash_wrong_length_is_rejected(db_session, seeded_user):
    s = UserSession(**_valid_browser_kwargs(seeded_user.id, csrf_token_hash="short"))
    db_session.add(s)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- ck_sessions_expires_after_created ------------------------------------------------

def test_expires_at_before_created_at_is_rejected(db_session, seeded_user):
    now = utc_now()
    s = UserSession(**_valid_desktop_kwargs(seeded_user.id))
    s.created_at = now
    s.expires_at = now - datetime.timedelta(seconds=1)
    db_session.add(s)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_expires_at_equal_to_created_at_is_rejected(db_session, seeded_user):
    now = utc_now()
    s = UserSession(**_valid_desktop_kwargs(seeded_user.id))
    s.created_at = now
    s.expires_at = now
    db_session.add(s)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- unique token_hash -----------------------------------------------------------------

def test_token_hash_must_be_unique(db_session, seeded_user):
    db_session.add(UserSession(**_valid_desktop_kwargs(seeded_user.id, token_hash=HASH64)))
    db_session.commit()

    db_session.add(UserSession(**_valid_desktop_kwargs(seeded_user.id, token_hash=HASH64)))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- static proof: migration targets the exact expected down_revision ---------------

_MIGRATIONS_DIR = _os.path.join(_os.path.dirname(__file__), "..", "migrations", "versions")


def test_migration_down_revision_is_current_head():
    matches = [f for f in _os.listdir(_MIGRATIONS_DIR) if f.startswith("d3fc3cb2ef8b_")]
    assert len(matches) == 1, matches
    with open(_os.path.join(_MIGRATIONS_DIR, matches[0])) as f:
        source = f.read()
    assert 'down_revision: Union[str, None] = "2327325e8143"' in source
    assert 'revision: str = "d3fc3cb2ef8b"' in source


def test_migration_touches_no_auth_behavior_symbols():
    """Static proof this stage really is schema-only: the migration file must not
    reference any routing, cookie-setting, Argon2, JWT, or rate-limiting *behavior* -
    the column/constraint name `csrf_token_hash` itself is expected and excluded, since
    the schema legitimately provisions storage for it without implementing any CSRF
    logic against it."""
    matches = [f for f in _os.listdir(_MIGRATIONS_DIR) if f.startswith("d3fc3cb2ef8b_")]
    with open(_os.path.join(_MIGRATIONS_DIR, matches[0])) as f:
        source = f.read()
    for forbidden in ("APIRouter", "set_cookie", "argon2", "Argon2", "import jwt", "rate_limit"):
        assert forbidden not in source, f"unexpected '{forbidden}' reference in a schema-only migration"
