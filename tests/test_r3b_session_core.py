"""Isolated regression tests for R3b-3 server-session lifecycle primitives."""

import os

_db_url = os.environ.get("DATABASE_URL", "")
_storage_dir = os.environ.get("STORAGE_DIR", "")

if not _db_url or "5432" in _db_url or "postgres" in _db_url.lower() or "ardor_pressure_test" in _db_url:
    raise RuntimeError(
        "DATABASE_URL is missing or looks like staging Postgres; use isolated SQLite."
    )
if not _storage_dir or os.path.normpath(_storage_dir) == "/data/storage":
    raise RuntimeError("STORAGE_DIR is missing or points at live storage.")

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.database import Base
from services.api.models import User, UserSession
from services.api.security import hash_opaque_secret
from services.api.session_service import (
    BROWSER_IDLE_LIFETIME,
    LAST_SEEN_TOUCH_INTERVAL,
    SESSION_ABSOLUTE_LIFETIME,
    RefreshOutcome,
    RevocationReason,
    SessionError,
    SessionInvariantError,
    create_browser_session,
    create_desktop_session,
    revoke_all_sessions,
    revoke_session,
    rotate_browser_session_secrets,
    rotate_desktop_refresh_secret,
    validate_browser_csrf,
    validate_browser_session,
    validate_desktop_session,
)


BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def user(db_session):
    record = User(username="session-user", hashed_password="x", role="viewer")
    db_session.add(record)
    db_session.commit()
    return record


def _record(db, session_id):
    db.expire_all()
    return db.query(UserSession).filter(UserSession.id == session_id).one()


def test_browser_issue_persists_only_hashes(db_session, user):
    issued = create_browser_session(db_session, user.id, now=BASE_TIME)
    record = _record(db_session, issued.session_id)

    assert record.channel == "browser"
    assert record.token_hash == hash_opaque_secret(issued.session_secret)
    assert record.csrf_token_hash == hash_opaque_secret(issued.csrf_secret)
    assert issued.session_secret not in (record.token_hash, record.csrf_token_hash)
    assert issued.csrf_secret not in (record.token_hash, record.csrf_token_hash)
    assert record.previous_token_hash is None
    assert issued.expires_at == BASE_TIME + SESSION_ABSOLUTE_LIFETIME


def test_desktop_issue_persists_only_refresh_hash(db_session, user):
    issued = create_desktop_session(db_session, user.id, now=BASE_TIME)
    record = _record(db_session, issued.session_id)

    assert record.channel == "desktop"
    assert record.token_hash == hash_opaque_secret(issued.refresh_secret)
    assert issued.refresh_secret != record.token_hash
    assert record.previous_token_hash is None
    assert record.csrf_token_hash is None
    assert issued.expires_at == BASE_TIME + SESSION_ABSOLUTE_LIFETIME


def test_session_creation_never_commits_and_caller_can_rollback(db_session, user, monkeypatch):
    def forbidden_commit():
        raise AssertionError("session service must not commit")

    monkeypatch.setattr(db_session, "commit", forbidden_commit)
    create_browser_session(db_session, user.id, now=BASE_TIME)
    db_session.rollback()
    assert db_session.query(UserSession).count() == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("device_label", "x" * 129),
        ("ip_address", "x" * 46),
        ("user_agent", "x" * 257),
    ],
)
def test_issue_rejects_oversized_metadata(db_session, user, field, value):
    with pytest.raises(ValueError):
        create_browser_session(db_session, user.id, now=BASE_TIME, **{field: value})
    assert db_session.query(UserSession).count() == 0


def test_valid_browser_session_and_csrf(db_session, user):
    issued = create_browser_session(db_session, user.id, now=BASE_TIME)
    result = validate_browser_session(
        db_session,
        issued.session_secret,
        now=BASE_TIME + timedelta(minutes=1),
    )
    assert result.ok is True
    assert result.session.id == issued.session_id
    assert result.last_seen_updated is False
    assert validate_browser_csrf(result.session, issued.csrf_secret) is True
    assert validate_browser_csrf(result.session, "x" * 43) is False


def test_browser_session_wrong_validly_shaped_secret_is_not_found(db_session, user):
    create_browser_session(db_session, user.id, now=BASE_TIME)
    result = validate_browser_session(db_session, "A" * 43, now=BASE_TIME)
    assert result.ok is False
    assert result.error is SessionError.NOT_FOUND


@pytest.mark.parametrize("bad", [None, "", "x" * 42, "x" * 44, "." * 43, "ä" * 43])
def test_browser_session_rejects_malformed_secret_without_lookup(db_session, bad):
    result = validate_browser_session(db_session, bad, now=BASE_TIME)
    assert result.ok is False
    assert result.error is SessionError.INVALID_SECRET


def test_browser_last_seen_not_touched_before_five_minutes(db_session, user):
    issued = create_browser_session(db_session, user.id, now=BASE_TIME)
    result = validate_browser_session(
        db_session,
        issued.session_secret,
        now=BASE_TIME + LAST_SEEN_TOUCH_INTERVAL - timedelta(seconds=1),
    )
    assert result.ok is True
    assert result.last_seen_updated is False
    assert _record(db_session, issued.session_id).last_seen_at.replace(tzinfo=timezone.utc) == BASE_TIME


def test_browser_last_seen_touched_at_five_minutes(db_session, user):
    issued = create_browser_session(db_session, user.id, now=BASE_TIME)
    touch_time = BASE_TIME + LAST_SEEN_TOUCH_INTERVAL
    result = validate_browser_session(db_session, issued.session_secret, now=touch_time)
    assert result.ok is True
    assert result.last_seen_updated is True
    stored = _record(db_session, issued.session_id).last_seen_at
    assert stored.replace(tzinfo=timezone.utc) == touch_time


def test_browser_idle_timeout_exact_boundary_is_rejected(db_session, user):
    issued = create_browser_session(db_session, user.id, now=BASE_TIME)
    result = validate_browser_session(
        db_session,
        issued.session_secret,
        now=BASE_TIME + BROWSER_IDLE_LIFETIME,
    )
    assert result.ok is False
    assert result.error is SessionError.IDLE_EXPIRED


def test_absolute_timeout_exact_boundary_is_rejected(db_session, user):
    issued = create_browser_session(db_session, user.id, now=BASE_TIME)
    result = validate_browser_session(
        db_session,
        issued.session_secret,
        now=BASE_TIME + SESSION_ABSOLUTE_LIFETIME,
    )
    assert result.ok is False
    assert result.error is SessionError.EXPIRED


def test_revoked_browser_session_is_rejected(db_session, user):
    issued = create_browser_session(db_session, user.id, now=BASE_TIME)
    assert revoke_session(
        db_session,
        user.id,
        issued.session_id,
        RevocationReason.LOGOUT,
        now=BASE_TIME + timedelta(minutes=1),
    ) is True
    result = validate_browser_session(
        db_session,
        issued.session_secret,
        now=BASE_TIME + timedelta(minutes=2),
    )
    assert result.ok is False
    assert result.error is SessionError.REVOKED


def test_desktop_validation_binds_channel_user_and_expiry(db_session, user):
    desktop = create_desktop_session(db_session, user.id, now=BASE_TIME)
    browser = create_browser_session(db_session, user.id, now=BASE_TIME)

    assert validate_desktop_session(db_session, desktop.session_id, user.id, now=BASE_TIME).ok is True
    wrong_user = validate_desktop_session(db_session, desktop.session_id, "other", now=BASE_TIME)
    assert wrong_user.error is SessionError.USER_MISMATCH
    wrong_channel = validate_desktop_session(db_session, browser.session_id, user.id, now=BASE_TIME)
    assert wrong_channel.error is SessionError.WRONG_CHANNEL
    expired = validate_desktop_session(
        db_session,
        desktop.session_id,
        user.id,
        now=BASE_TIME + SESSION_ABSOLUTE_LIFETIME,
    )
    assert expired.error is SessionError.EXPIRED


def test_desktop_refresh_rotation_is_atomic_and_hash_only(db_session, user):
    issued = create_desktop_session(db_session, user.id, now=BASE_TIME)
    rotated = rotate_desktop_refresh_secret(
        db_session,
        issued.refresh_secret,
        now=BASE_TIME + timedelta(minutes=1),
    )
    assert rotated.outcome is RefreshOutcome.SUCCESS
    assert rotated.session_id == issued.session_id
    assert rotated.refresh_secret and rotated.refresh_secret != issued.refresh_secret

    record = _record(db_session, issued.session_id)
    assert record.previous_token_hash == hash_opaque_secret(issued.refresh_secret)
    assert record.token_hash == hash_opaque_secret(rotated.refresh_secret)
    assert issued.refresh_secret not in (record.token_hash, record.previous_token_hash)
    assert rotated.refresh_secret not in (record.token_hash, record.previous_token_hash)


def test_replaying_previous_desktop_refresh_revokes_session(db_session, user):
    issued = create_desktop_session(db_session, user.id, now=BASE_TIME)
    rotated = rotate_desktop_refresh_secret(
        db_session,
        issued.refresh_secret,
        now=BASE_TIME + timedelta(minutes=1),
    )
    replay = rotate_desktop_refresh_secret(
        db_session,
        issued.refresh_secret,
        now=BASE_TIME + timedelta(minutes=2),
    )
    assert replay.outcome is RefreshOutcome.REUSE_DETECTED
    assert replay.refresh_secret is None

    record = _record(db_session, issued.session_id)
    assert record.revoked_reason == RevocationReason.REUSE_DETECTED.value
    assert rotate_desktop_refresh_secret(
        db_session,
        rotated.refresh_secret,
        now=BASE_TIME + timedelta(minutes=3),
    ).outcome is RefreshOutcome.REVOKED


def test_invalid_desktop_refresh_does_not_mutate(db_session, user):
    issued = create_desktop_session(db_session, user.id, now=BASE_TIME)
    before = _record(db_session, issued.session_id).token_hash
    result = rotate_desktop_refresh_secret(db_session, "A" * 43, now=BASE_TIME)
    assert result.outcome is RefreshOutcome.INVALID
    record = _record(db_session, issued.session_id)
    assert record.token_hash == before
    assert record.previous_token_hash is None
    assert record.revoked_at is None


def test_expired_desktop_refresh_does_not_rotate(db_session, user):
    issued = create_desktop_session(db_session, user.id, now=BASE_TIME)
    result = rotate_desktop_refresh_secret(
        db_session,
        issued.refresh_secret,
        now=BASE_TIME + SESSION_ABSOLUTE_LIFETIME,
    )
    assert result.outcome is RefreshOutcome.EXPIRED
    record = _record(db_session, issued.session_id)
    assert record.previous_token_hash is None
    assert record.token_hash == hash_opaque_secret(issued.refresh_secret)


def test_duplicate_previous_hash_is_an_invariant_failure(db_session, user):
    first = create_desktop_session(db_session, user.id, now=BASE_TIME)
    second = create_desktop_session(db_session, user.id, now=BASE_TIME)
    duplicate = hash_opaque_secret("A" * 43)
    first_record = db_session.query(UserSession).filter(UserSession.id == first.session_id).one()
    second_record = db_session.query(UserSession).filter(UserSession.id == second.session_id).one()
    first_record.previous_token_hash = duplicate
    second_record.previous_token_hash = duplicate
    db_session.flush()

    with pytest.raises(SessionInvariantError):
        rotate_desktop_refresh_secret(db_session, "A" * 43, now=BASE_TIME)


def test_browser_secret_rotation_invalidates_old_pair(db_session, user):
    issued = create_browser_session(db_session, user.id, now=BASE_TIME)
    rotated = rotate_browser_session_secrets(
        db_session,
        issued.session_id,
        user.id,
        issued.session_secret,
        now=BASE_TIME + timedelta(minutes=1),
    )
    assert validate_browser_session(
        db_session,
        issued.session_secret,
        now=BASE_TIME + timedelta(minutes=2),
    ).error is SessionError.NOT_FOUND
    new_result = validate_browser_session(
        db_session,
        rotated.session_secret,
        now=BASE_TIME + timedelta(minutes=2),
    )
    assert new_result.ok is True
    assert validate_browser_csrf(new_result.session, issued.csrf_secret) is False
    assert validate_browser_csrf(new_result.session, rotated.csrf_secret) is True


def test_browser_rotation_guard_rejects_wrong_user_without_mutation(db_session, user):
    issued = create_browser_session(db_session, user.id, now=BASE_TIME)
    before = _record(db_session, issued.session_id).token_hash
    with pytest.raises(SessionInvariantError):
        rotate_browser_session_secrets(
            db_session,
            issued.session_id,
            "another-user",
            issued.session_secret,
            now=BASE_TIME + timedelta(minutes=1),
        )
    assert _record(db_session, issued.session_id).token_hash == before


def test_revoke_one_is_ownership_scoped_and_idempotent(db_session, user):
    issued = create_browser_session(db_session, user.id, now=BASE_TIME)
    assert revoke_session(
        db_session,
        "another-user",
        issued.session_id,
        RevocationReason.LOGOUT,
        now=BASE_TIME,
    ) is False
    assert revoke_session(
        db_session,
        user.id,
        issued.session_id,
        RevocationReason.LOGOUT,
        now=BASE_TIME,
    ) is True
    assert revoke_session(
        db_session,
        user.id,
        issued.session_id,
        RevocationReason.LOGOUT,
        now=BASE_TIME,
    ) is False


def test_revoke_all_can_preserve_current_session(db_session, user):
    first = create_browser_session(db_session, user.id, now=BASE_TIME)
    second = create_desktop_session(db_session, user.id, now=BASE_TIME)
    third = create_desktop_session(db_session, user.id, now=BASE_TIME)

    count = revoke_all_sessions(
        db_session,
        user.id,
        RevocationReason.PASSWORD_CHANGE,
        except_session_id=first.session_id,
        now=BASE_TIME + timedelta(minutes=1),
    )
    assert count == 2
    assert _record(db_session, first.session_id).revoked_at is None
    assert _record(db_session, second.session_id).revoked_reason == "password_change"
    assert _record(db_session, third.session_id).revoked_reason == "password_change"


def test_mutations_are_rolled_back_as_one_caller_owned_transaction(db_session, user):
    issued = create_desktop_session(db_session, user.id, now=BASE_TIME)
    db_session.commit()  # establishes the test's baseline, outside the service call
    original_hash = _record(db_session, issued.session_id).token_hash

    rotate_desktop_refresh_secret(
        db_session,
        issued.refresh_secret,
        now=BASE_TIME + timedelta(minutes=1),
    )
    db_session.rollback()

    record = _record(db_session, issued.session_id)
    assert record.token_hash == original_hash
    assert record.previous_token_hash is None


def test_session_service_contains_no_commit_or_rollback_calls():
    import inspect
    import services.api.session_service as module

    source = inspect.getsource(module)
    assert ".commit(" not in source
    assert ".rollback(" not in source
