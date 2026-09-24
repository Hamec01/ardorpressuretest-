"""Transaction-neutral server-session lifecycle primitives for R3.

Every mutating function flushes its work but deliberately never commits or rolls back.
The future HTTP route owns the transaction and can atomically combine session changes
with password/user/audit changes. Raw secrets are returned only at issuance/rotation;
they are never persisted or included in failure results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from string import ascii_letters, digits
from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from services.api.models import UserSession
from services.api.security import compare_secret_hashes, generate_opaque_secret, hash_opaque_secret


BROWSER_IDLE_LIFETIME = timedelta(hours=12)
SESSION_ABSOLUTE_LIFETIME = timedelta(days=30)
LAST_SEEN_TOUCH_INTERVAL = timedelta(minutes=5)
OPAQUE_SECRET_LENGTH = 43  # token_urlsafe(32), without padding
_OPAQUE_SECRET_ALPHABET = frozenset(ascii_letters + digits + "-_")


class SessionError(str, Enum):
    INVALID_SECRET = "invalid_secret"
    NOT_FOUND = "not_found"
    REVOKED = "revoked"
    EXPIRED = "expired"
    IDLE_EXPIRED = "idle_expired"
    WRONG_CHANNEL = "wrong_channel"
    USER_MISMATCH = "user_mismatch"
    CSRF_INVALID = "csrf_invalid"


class RefreshOutcome(str, Enum):
    SUCCESS = "success"
    INVALID = "invalid"
    REVOKED = "revoked"
    EXPIRED = "expired"
    REUSE_DETECTED = "reuse_detected"


class RevocationReason(str, Enum):
    LOGOUT = "logout"
    REVOKE_ALL = "revoke_all"
    PASSWORD_CHANGE = "password_change"
    DEACTIVATED = "deactivated"
    ROLE_CHANGED = "role_changed"
    ROTATED = "rotated"
    ADMIN_REVOKE = "admin_revoke"
    REUSE_DETECTED = "reuse_detected"


class SessionInvariantError(RuntimeError):
    """Raised for impossible database states; caller must roll back the transaction."""


@dataclass(frozen=True)
class BrowserSessionIssue:
    session_id: str
    session_secret: str
    csrf_secret: str
    expires_at: datetime


@dataclass(frozen=True)
class DesktopSessionIssue:
    session_id: str
    refresh_secret: str
    expires_at: datetime


@dataclass
class SessionCheckResult:
    ok: bool
    session: Optional[UserSession] = None
    error: Optional[SessionError] = None
    last_seen_updated: bool = False


@dataclass(frozen=True)
class BrowserRotationResult:
    session_id: str
    session_secret: str
    csrf_secret: str


@dataclass(frozen=True)
class DesktopRefreshResult:
    outcome: RefreshOutcome
    session_id: Optional[str] = None
    refresh_secret: Optional[str] = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalized_now(now: Optional[datetime]) -> datetime:
    value = now or _utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalized_db_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _valid_opaque_secret_shape(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == OPAQUE_SECRET_LENGTH
        and all(char in _OPAQUE_SECRET_ALPHABET for char in value)
    )


def _required_identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _optional_text(value: Optional[str], label: str, max_length: int) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > max_length:
        raise ValueError(f"{label} must be a string of at most {max_length} characters")
    return value


def create_browser_session(
    db: Session,
    user_id: str,
    *,
    device_label: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    now: Optional[datetime] = None,
) -> BrowserSessionIssue:
    current_time = _normalized_now(now)
    session_secret = generate_opaque_secret()
    csrf_secret = generate_opaque_secret()
    record = UserSession(
        user_id=_required_identifier(user_id, "user_id"),
        channel="browser",
        token_hash=hash_opaque_secret(session_secret),
        previous_token_hash=None,
        csrf_token_hash=hash_opaque_secret(csrf_secret),
        created_at=current_time,
        last_seen_at=current_time,
        expires_at=current_time + SESSION_ABSOLUTE_LIFETIME,
        device_label=_optional_text(device_label, "device_label", 128),
        ip_address=_optional_text(ip_address, "ip_address", 45),
        user_agent=_optional_text(user_agent, "user_agent", 256),
    )
    db.add(record)
    db.flush()
    return BrowserSessionIssue(record.id, session_secret, csrf_secret, record.expires_at)


def create_desktop_session(
    db: Session,
    user_id: str,
    *,
    device_label: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    now: Optional[datetime] = None,
) -> DesktopSessionIssue:
    current_time = _normalized_now(now)
    refresh_secret = generate_opaque_secret()
    record = UserSession(
        user_id=_required_identifier(user_id, "user_id"),
        channel="desktop",
        token_hash=hash_opaque_secret(refresh_secret),
        previous_token_hash=None,
        csrf_token_hash=None,
        created_at=current_time,
        last_seen_at=current_time,
        expires_at=current_time + SESSION_ABSOLUTE_LIFETIME,
        device_label=_optional_text(device_label, "device_label", 128),
        ip_address=_optional_text(ip_address, "ip_address", 45),
        user_agent=_optional_text(user_agent, "user_agent", 256),
    )
    db.add(record)
    db.flush()
    return DesktopSessionIssue(record.id, refresh_secret, record.expires_at)


def _state_error(record: UserSession, now: datetime) -> Optional[SessionError]:
    if record.revoked_at is not None:
        return SessionError.REVOKED
    if now >= _normalized_db_time(record.expires_at):
        return SessionError.EXPIRED
    return None


def validate_browser_session(
    db: Session,
    session_secret,
    *,
    now: Optional[datetime] = None,
) -> SessionCheckResult:
    if not _valid_opaque_secret_shape(session_secret):
        return SessionCheckResult(ok=False, error=SessionError.INVALID_SECRET)
    presented_hash = hash_opaque_secret(session_secret)
    record = (
        db.query(UserSession)
        .filter(UserSession.token_hash == presented_hash)
        .one_or_none()
    )
    if record is None:
        return SessionCheckResult(ok=False, error=SessionError.NOT_FOUND)
    if record.channel != "browser":
        return SessionCheckResult(ok=False, error=SessionError.WRONG_CHANNEL)

    current_time = _normalized_now(now)
    error = _state_error(record, current_time)
    if error is not None:
        return SessionCheckResult(ok=False, error=error)

    last_seen = _normalized_db_time(record.last_seen_at)
    if current_time >= last_seen + BROWSER_IDLE_LIFETIME:
        return SessionCheckResult(ok=False, error=SessionError.IDLE_EXPIRED)

    touched = current_time - last_seen >= LAST_SEEN_TOUCH_INTERVAL
    if touched:
        record.last_seen_at = current_time
        db.flush()
    return SessionCheckResult(ok=True, session=record, last_seen_updated=touched)


def validate_browser_csrf(record: UserSession, csrf_secret) -> bool:
    if record.channel != "browser" or not record.csrf_token_hash:
        return False
    if not _valid_opaque_secret_shape(csrf_secret):
        return False
    return compare_secret_hashes(hash_opaque_secret(csrf_secret), record.csrf_token_hash)


def validate_desktop_session(
    db: Session,
    session_id: str,
    user_id: str,
    *,
    now: Optional[datetime] = None,
) -> SessionCheckResult:
    if not isinstance(session_id, str) or not session_id:
        return SessionCheckResult(ok=False, error=SessionError.NOT_FOUND)
    record = db.query(UserSession).filter(UserSession.id == session_id).one_or_none()
    if record is None:
        return SessionCheckResult(ok=False, error=SessionError.NOT_FOUND)
    if record.channel != "desktop":
        return SessionCheckResult(ok=False, error=SessionError.WRONG_CHANNEL)
    if not isinstance(user_id, str) or record.user_id != user_id:
        return SessionCheckResult(ok=False, error=SessionError.USER_MISMATCH)
    error = _state_error(record, _normalized_now(now))
    if error is not None:
        return SessionCheckResult(ok=False, error=error)
    return SessionCheckResult(ok=True, session=record)


def rotate_desktop_refresh_secret(
    db: Session,
    presented_secret,
    *,
    now: Optional[datetime] = None,
) -> DesktopRefreshResult:
    if not _valid_opaque_secret_shape(presented_secret):
        return DesktopRefreshResult(RefreshOutcome.INVALID)
    presented_hash = hash_opaque_secret(presented_secret)
    current_time = _normalized_now(now)

    current = (
        db.query(UserSession)
        .filter(UserSession.channel == "desktop", UserSession.token_hash == presented_hash)
        .with_for_update()
        .one_or_none()
    )
    if current is not None:
        error = _state_error(current, current_time)
        if error == SessionError.REVOKED:
            return DesktopRefreshResult(RefreshOutcome.REVOKED, session_id=current.id)
        if error == SessionError.EXPIRED:
            return DesktopRefreshResult(RefreshOutcome.EXPIRED, session_id=current.id)

        new_secret = generate_opaque_secret()
        new_hash = hash_opaque_secret(new_secret)
        result = db.execute(
            update(UserSession)
            .where(
                UserSession.id == current.id,
                UserSession.channel == "desktop",
                UserSession.token_hash == presented_hash,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > current_time,
            )
            .values(
                previous_token_hash=presented_hash,
                token_hash=new_hash,
                last_seen_at=current_time,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise SessionInvariantError("desktop refresh rotation lost its guarded row")
        db.flush()
        return DesktopRefreshResult(RefreshOutcome.SUCCESS, current.id, new_secret)

    previous_matches = (
        db.query(UserSession)
        .filter(
            UserSession.channel == "desktop",
            UserSession.previous_token_hash == presented_hash,
        )
        .with_for_update()
        .all()
    )
    if not previous_matches:
        return DesktopRefreshResult(RefreshOutcome.INVALID)
    if len(previous_matches) != 1:
        raise SessionInvariantError("desktop previous-token hash matched multiple sessions")

    previous = previous_matches[0]
    if previous.revoked_at is not None:
        return DesktopRefreshResult(RefreshOutcome.REVOKED, session_id=previous.id)
    if current_time >= _normalized_db_time(previous.expires_at):
        return DesktopRefreshResult(RefreshOutcome.EXPIRED, session_id=previous.id)

    result = db.execute(
        update(UserSession)
        .where(
            UserSession.id == previous.id,
            UserSession.channel == "desktop",
            UserSession.previous_token_hash == presented_hash,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=current_time, revoked_reason=RevocationReason.REUSE_DETECTED.value)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise SessionInvariantError("desktop reuse revocation lost its guarded row")
    db.flush()
    return DesktopRefreshResult(RefreshOutcome.REUSE_DETECTED, session_id=previous.id)


def rotate_browser_session_secrets(
    db: Session,
    session_id: str,
    user_id: str,
    current_session_secret,
    *,
    now: Optional[datetime] = None,
) -> BrowserRotationResult:
    if not _valid_opaque_secret_shape(current_session_secret):
        raise ValueError("current browser session secret is invalid")
    current_hash = hash_opaque_secret(current_session_secret)
    current_time = _normalized_now(now)
    new_session_secret = generate_opaque_secret()
    new_csrf_secret = generate_opaque_secret()
    result = db.execute(
        update(UserSession)
        .where(
            UserSession.id == _required_identifier(session_id, "session_id"),
            UserSession.user_id == _required_identifier(user_id, "user_id"),
            UserSession.channel == "browser",
            UserSession.token_hash == current_hash,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > current_time,
        )
        .values(
            token_hash=hash_opaque_secret(new_session_secret),
            csrf_token_hash=hash_opaque_secret(new_csrf_secret),
            last_seen_at=current_time,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise SessionInvariantError("browser rotation did not match exactly one active session")
    db.flush()
    return BrowserRotationResult(session_id, new_session_secret, new_csrf_secret)


def revoke_session(
    db: Session,
    user_id: str,
    session_id: str,
    reason: RevocationReason,
    *,
    now: Optional[datetime] = None,
) -> bool:
    if not isinstance(reason, RevocationReason):
        raise ValueError("reason must be a RevocationReason")
    result = db.execute(
        update(UserSession)
        .where(
            UserSession.id == _required_identifier(session_id, "session_id"),
            UserSession.user_id == _required_identifier(user_id, "user_id"),
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=_normalized_now(now), revoked_reason=reason.value)
        .execution_options(synchronize_session=False)
    )
    db.flush()
    return result.rowcount == 1


def revoke_all_sessions(
    db: Session,
    user_id: str,
    reason: RevocationReason,
    *,
    except_session_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> int:
    if not isinstance(reason, RevocationReason):
        raise ValueError("reason must be a RevocationReason")
    statement = update(UserSession).where(
        UserSession.user_id == _required_identifier(user_id, "user_id"),
        UserSession.revoked_at.is_(None),
    )
    if except_session_id is not None:
        statement = statement.where(
            UserSession.id != _required_identifier(except_session_id, "except_session_id")
        )
    result = db.execute(
        statement
        .values(revoked_at=_normalized_now(now), revoked_reason=reason.value)
        .execution_options(synchronize_session=False)
    )
    db.flush()
    return result.rowcount
