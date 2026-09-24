import hashlib
import math
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, text
from sqlalchemy.orm import Session
from services.api.auth import (
    AuthenticationMethod,
    AuthenticatedRequest,
    DUMMY_ARGON2_HASH,
    check_password_with_upgrade,
    create_access_token,
    hash_password,
    require_authentication_context,
    require_mutating_authentication_context,
    require_role,
    validate_new_password,
    verify_password,
)
from services.api.database import get_db
from services.api.config import settings
from services.api.http_security import clear_browser_auth_cookies, set_browser_auth_cookies
from services.api.models import AuditEvent, User, UserSession
from services.api.session_service import (
    BROWSER_IDLE_LIFETIME,
    RevocationReason,
    create_browser_session,
    revoke_all_sessions,
    revoke_session,
    rotate_browser_session_secrets,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    full_name: str | None
    role: str
    email: str | None
    must_change_password: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class LogoutResponse(BaseModel):
    status: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class ChangePasswordResponse(BaseModel):
    status: str
    reauthentication_required: bool


class SessionResponse(BaseModel):
    id: str
    channel: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    device_label: str | None
    is_current: bool


class RevokeSessionResponse(BaseModel):
    status: str


_LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
_LOGIN_FAILURE_LIMIT = 5


def _audit_event(
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


def _enforce_login_rate_limit(db: Session, username: str, now: datetime) -> None:
    """Serialize and enforce the rolling per-username login-failure window.

    PostgreSQL's transaction-scoped advisory lock makes the count + subsequent
    success/failure commit one serialized operation per normalized username. This
    prevents concurrent requests from all observing four failures and then performing
    expensive Argon2 work together. SQLite is used only by isolated tests and has no
    equivalent advisory-lock function.
    """
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _login_rate_lock_key(username)},
        )

    cutoff = now - _LOGIN_FAILURE_WINDOW
    recent_failures = (
        db.query(AuditEvent.created_at)
        .filter(
            AuditEvent.action == "login_failed",
            AuditEvent.actor_name == username,
            AuditEvent.created_at > cutoff,
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(_LOGIN_FAILURE_LIMIT)
        .all()
    )
    if len(recent_failures) < _LOGIN_FAILURE_LIMIT:
        return

    fifth_newest = _normalized_db_time(recent_failures[-1][0])
    retry_after = max(
        1,
        math.ceil((fifth_newest + _LOGIN_FAILURE_WINDOW - now).total_seconds()),
    )
    db.rollback()
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many login attempts. Try again later.",
        headers={"Retry-After": str(retry_after)},
    )


def _require_account_access(
    context: AuthenticatedRequest,
    *,
    allow_must_change_password: bool = False,
) -> None:
    if context.user.role not in {"admin", "foreman", "viewer"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if context.user.must_change_password and not allow_must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required",
        )


def _commit_auth_changes(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        )


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Authenticate, retain transitional Bearer support, and issue browser cookies
    only to the explicitly configured first-party origin.

    The origin-gated cookie issuance lets the backend land before the web cutover:
    existing clients still receive the legacy Bearer response, while an untrusted
    origin can never cause ambient authentication cookies to be installed.
    """
    username = req.username.strip()
    now = datetime.now(timezone.utc)
    _enforce_login_rate_limit(db, username, now)
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
            _audit_event(
                user=None,
                action="login_failed",
                actor_name=username,
                details={"channel": "browser", "ip": request.client.host if request.client else None},
            )
        )
        _commit_auth_changes(db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    if password_check.upgraded_hash is not None:
        user.hashed_password = password_check.upgraded_hash
    user.last_login_at = now

    browser_issue = None
    if request.headers.get("origin") == settings.public_origin:
        browser_issue = create_browser_session(
            db,
            str(user.id),
            ip_address=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent") or "")[:256] or None,
            now=now,
        )

    token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name
    })

    db.add(
        _audit_event(
            user=user,
            action="login",
            actor_name=user.full_name or user.username,
            details={
                "channel": "browser" if browser_issue is not None else "legacy_bearer",
                "ip": request.client.host if request.client else None,
                "role": user.role,
            },
        )
    )
    _commit_auth_changes(db)

    if browser_issue is not None:
        set_browser_auth_cookies(response, browser_issue.session_secret, browser_issue.csrf_secret)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@router.get("/me", response_model=UserResponse)
def get_me(context: AuthenticatedRequest = Depends(require_authentication_context)):
    """Возвращает профиль текущего пользователя."""
    _require_account_access(context, allow_must_change_password=True)
    return context.user


@router.post("/logout", response_model=LogoutResponse)
def logout(
    response: Response,
    context: AuthenticatedRequest = Depends(require_mutating_authentication_context),
    db: Session = Depends(get_db),
):
    """Revoke the current server-backed session and clear browser cookies.

    Transitional legacy Bearer tokens have no backing row and therefore cannot be
    revoked server-side; their temporary limitation remains explicit.
    """
    if context.session_id is not None:
        if not revoke_session(
            db,
            str(context.user.id),
            context.session_id,
            RevocationReason.LOGOUT,
        ):
            db.rollback()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid")
    db.add(
        _audit_event(
            user=context.user,
            action="logout",
            actor_name=context.user.full_name or context.user.username,
            details={"channel": context.method.value},
        )
    )
    _commit_auth_changes(db)
    clear_browser_auth_cookies(response)
    return {"status": "ok"}


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    response: Response,
    context: AuthenticatedRequest = Depends(require_mutating_authentication_context),
    db: Session = Depends(get_db),
):
    """Change the caller's password and invalidate every pre-change session secret."""
    _require_account_access(context, allow_must_change_password=True)
    validation_error = validate_new_password(req.new_password)
    if validation_error is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=validation_error)

    password_check = check_password_with_upgrade(
        req.current_password,
        context.user.hashed_password,
    )
    if not password_check.ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    context.user.hashed_password = hash_password(req.new_password)
    context.user.must_change_password = False
    browser_rotation = None
    if context.method is AuthenticationMethod.BROWSER_SESSION:
        current_secret = request.cookies.get(settings.session_cookie_name)
        revoke_all_sessions(
            db,
            str(context.user.id),
            RevocationReason.PASSWORD_CHANGE,
            except_session_id=context.session_id,
        )
        browser_rotation = rotate_browser_session_secrets(
            db,
            context.session_id,
            str(context.user.id),
            current_secret,
        )
    else:
        # A desktop access token cannot rotate the separate opaque refresh secret,
        # and a transitional legacy Bearer has no session row at all. Revoke every
        # server-backed session and require a new login for those channels.
        revoke_all_sessions(
            db,
            str(context.user.id),
            RevocationReason.PASSWORD_CHANGE,
        )

    db.add(
        _audit_event(
            user=context.user,
            action="password_changed",
            actor_name=context.user.full_name or context.user.username,
            details={"channel": context.method.value},
        )
    )
    _commit_auth_changes(db)

    if browser_rotation is not None:
        set_browser_auth_cookies(
            response,
            browser_rotation.session_secret,
            browser_rotation.csrf_secret,
        )
    else:
        clear_browser_auth_cookies(response)
    return {
        "status": "ok",
        "reauthentication_required": browser_rotation is None,
    }


@router.get("/sessions", response_model=List[SessionResponse])
def list_sessions(
    context: AuthenticatedRequest = Depends(require_authentication_context),
    db: Session = Depends(get_db),
):
    """List the caller's currently usable server-backed sessions without secrets."""
    _require_account_access(context)
    now = datetime.now(timezone.utc)
    rows = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == context.user.id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
            or_(
                UserSession.channel != "browser",
                UserSession.last_seen_at > now - BROWSER_IDLE_LIFETIME,
            ),
        )
        .order_by(UserSession.created_at.desc())
        .all()
    )
    return [
        SessionResponse(
            id=row.id,
            channel=row.channel,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
            device_label=row.device_label,
            is_current=row.id == context.session_id,
        )
        for row in rows
    ]


@router.delete("/sessions/{session_id}", response_model=RevokeSessionResponse)
def delete_session(
    session_id: str,
    response: Response,
    context: AuthenticatedRequest = Depends(require_mutating_authentication_context),
    db: Session = Depends(get_db),
):
    """Revoke one caller-owned session; another user's id is indistinguishable from missing."""
    _require_account_access(context)
    if not revoke_session(
        db,
        str(context.user.id),
        session_id,
        RevocationReason.LOGOUT,
    ):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    db.add(
        _audit_event(
            user=context.user,
            action="session_revoked",
            actor_name=context.user.full_name or context.user.username,
            details={"current_session": session_id == context.session_id},
        )
    )
    _commit_auth_changes(db)
    if session_id == context.session_id:
        clear_browser_auth_cookies(response)
    return {"status": "ok"}


@router.get("/users", response_model=List[UserResponse])
def list_users(
    user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """Список активных пользователей системы (только Admin)."""
    return db.query(User).filter(User.is_active == True).all()
