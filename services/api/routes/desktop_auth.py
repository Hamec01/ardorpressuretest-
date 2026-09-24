"""Native desktop authentication routes: login and rotating refresh."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.api.auth import (
    DUMMY_ARGON2_HASH,
    DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS,
    check_password_with_upgrade,
    create_desktop_access_token,
    verify_password,
)
from services.api.database import get_db
from services.api.auth_operations import (
    commit_auth_changes,
    enforce_login_rate_limit,
    new_auth_audit_event,
)
from services.api.models import AuditEvent, User, UserSession
from services.api.routes.auth import UserResponse
from services.api.session_service import (
    RefreshOutcome,
    RevocationReason,
    create_desktop_session,
    revoke_session,
    rotate_desktop_refresh_secret,
)


router = APIRouter(prefix="/api/v1/desktop", tags=["Desktop Authentication"])


class DesktopLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    device_label: str | None = Field(default=None, max_length=128)


class DesktopLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserResponse


class DesktopRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=256)


class DesktopRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


def _desktop_refresh_rejected() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token invalid or expired",
    )


@router.post("/login", response_model=DesktopLoginResponse)
def desktop_login(
    req: DesktopLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate a native client and issue a session-bound access/refresh pair."""
    username = req.username.strip()
    now = datetime.now(timezone.utc)
    enforce_login_rate_limit(db, username, now)
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    password_check = (
        check_password_with_upgrade(req.password, user.hashed_password)
        if user is not None
        else None
    )
    if user is None:
        verify_password(req.password, DUMMY_ARGON2_HASH)
    if user is None or password_check is None or not password_check.ok:
        db.add(
            new_auth_audit_event(
                user=None,
                action="login_failed",
                actor_name=username,
                details={"channel": "desktop", "ip": request.client.host if request.client else None},
            )
        )
        commit_auth_changes(db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if password_check.upgraded_hash is not None:
        user.hashed_password = password_check.upgraded_hash
    user.last_login_at = now
    issued = create_desktop_session(
        db,
        str(user.id),
        device_label=req.device_label,
        ip_address=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:256] or None,
        now=now,
    )
    access_token = create_desktop_access_token(str(user.id), issued.session_id)
    db.add(
        new_auth_audit_event(
            user=user,
            action="login",
            actor_name=user.full_name or user.username,
            details={"channel": "desktop", "role": user.role},
        )
    )
    commit_auth_changes(db)
    return {
        "access_token": access_token,
        "refresh_token": issued.refresh_secret,
        "token_type": "bearer",
        "expires_in": DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS,
        "user": user,
    }


@router.post("/token/refresh", response_model=DesktopRefreshResponse)
def desktop_refresh(req: DesktopRefreshRequest, db: Session = Depends(get_db)):
    """Rotate a desktop refresh secret exactly once and issue a fresh access JWT."""
    if "." in req.refresh_token:
        raise _desktop_refresh_rejected()

    rotated = rotate_desktop_refresh_secret(db, req.refresh_token)
    if rotated.outcome is RefreshOutcome.REUSE_DETECTED:
        db.add(
            AuditEvent(
                entity_type="session",
                entity_id=rotated.session_id,
                action="desktop_refresh_reuse_detected",
                user_id=None,
                actor_name="desktop_refresh_guard",
                details_json={"reason": "reuse_detected"},
            )
        )
        commit_auth_changes(db)
        raise _desktop_refresh_rejected()
    if rotated.outcome is not RefreshOutcome.SUCCESS:
        db.rollback()
        raise _desktop_refresh_rejected()

    record = db.get(UserSession, rotated.session_id)
    user = db.get(User, record.user_id) if record is not None else None
    if record is None or user is None or not user.is_active:
        if record is not None:
            revoke_session(
                db,
                record.user_id,
                record.id,
                RevocationReason.DEACTIVATED,
            )
            commit_auth_changes(db)
        else:
            db.rollback()
        raise _desktop_refresh_rejected()

    access_token = create_desktop_access_token(str(user.id), record.id)
    commit_auth_changes(db)
    return {
        "access_token": access_token,
        "refresh_token": rotated.refresh_secret,
        "token_type": "bearer",
        "expires_in": DESKTOP_ACCESS_TOKEN_LIFETIME_SECONDS,
    }
