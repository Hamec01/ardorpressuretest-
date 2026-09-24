"""Shared transactional helpers for browser and desktop authentication routes."""

import hashlib
import math
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.api.models import AuditEvent, User


LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
LOGIN_FAILURE_LIMIT = 5


def new_auth_audit_event(
    *,
    user: User | None,
    action: str,
    actor_name: str,
    details: dict,
) -> AuditEvent:
    return AuditEvent(
        entity_type="user",
        entity_id=str(user.id) if user is not None else actor_name,
        action=action,
        user_id=str(user.id) if user is not None else None,
        actor_name=actor_name,
        details_json=details,
    )


def _normalized_db_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _login_rate_lock_key(username: str) -> int:
    digest = hashlib.sha256(f"ardor-login:{username}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


def enforce_login_rate_limit(db: Session, username: str, now: datetime) -> None:
    """Atomically enforce the rolling failure window for one normalized username."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _login_rate_lock_key(username)},
        )

    cutoff = now - LOGIN_FAILURE_WINDOW
    recent_failures = (
        db.query(AuditEvent.created_at)
        .filter(
            AuditEvent.action == "login_failed",
            AuditEvent.actor_name == username,
            AuditEvent.created_at > cutoff,
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(LOGIN_FAILURE_LIMIT)
        .all()
    )
    if len(recent_failures) < LOGIN_FAILURE_LIMIT:
        return

    fifth_newest = _normalized_db_time(recent_failures[-1][0])
    retry_after = max(
        1,
        math.ceil((fifth_newest + LOGIN_FAILURE_WINDOW - now).total_seconds()),
    )
    db.rollback()
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many login attempts. Try again later.",
        headers={"Retry-After": str(retry_after)},
    )


def commit_auth_changes(db: Session) -> None:
    """Commit an auth transaction without exposing database exception details."""
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )
