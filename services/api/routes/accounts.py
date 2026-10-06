"""Admin account management and one-time password links (docs/ACCESS_PLAN_R4-R7.md stage 1).

Admin only, except the two public password-link routes, which are authorised by the
256-bit link token itself. Accounts are never physically deleted (ADR-005 §4, §12):
they are deactivated. Passwords and link tokens never reach logs or audit events.
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, text, update
from sqlalchemy.orm import Session

from services.api.auth import hash_password, require_role, validate_new_password
from services.api.auth_operations import commit_auth_changes
from services.api.config import settings
from services.api.database import get_db
from services.api.models import AuditEvent, PasswordLink, User, UserSession
from services.api.security import generate_opaque_secret, hash_opaque_secret
from services.api.session_service import BROWSER_IDLE_LIFETIME, RevocationReason, revoke_all_sessions

router = APIRouter(prefix="/api/v1/auth", tags=["Accounts"])

ACCOUNT_ROLES = ("admin", "foreman", "viewer")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
PASSWORD_LINK_LIFETIME = timedelta(hours=72)

Role = Literal["admin", "foreman", "viewer"]


class PasswordLinkState(BaseModel):
    status: Literal["pending", "none"]
    purpose: Optional[str] = None
    expires_at: Optional[datetime] = None


class AccountResponse(BaseModel):
    id: str
    username: str
    full_name: Optional[str]
    email: Optional[str]
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    active_sessions: int
    password_link: PasswordLinkState


class IssuedPasswordLink(BaseModel):
    url: str
    purpose: str
    expires_at: datetime


class AccountCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=128)
    email: Optional[str] = Field(default=None, max_length=128)
    role: Role
    # Admin ticked "set the password myself": otherwise a one-time link is issued.
    password: Optional[str] = Field(default=None, max_length=128)
    require_password_change: bool = True


class AccountCreateResponse(BaseModel):
    account: AccountResponse
    password_link: Optional[IssuedPasswordLink] = None


class AccountUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    email: Optional[str] = Field(default=None, max_length=128)
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class AdminSetPasswordRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    require_password_change: bool = True


class PasswordLinkInfo(BaseModel):
    username: str
    full_name: Optional[str]
    purpose: str
    expires_at: datetime


class PasswordLinkUseRequest(BaseModel):
    new_password: str = Field(min_length=1, max_length=128)


class PasswordLinkUseResponse(BaseModel):
    status: str
    username: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _actor_name(user: User) -> str:
    return user.full_name or user.username


def _audit(db: Session, actor: Optional[User], target: User, action: str, details: dict) -> None:
    db.add(
        AuditEvent(
            entity_type="user",
            entity_id=str(target.id),
            action=action,
            user_id=str(actor.id) if actor is not None else None,
            actor_name=_actor_name(actor) if actor is not None else _actor_name(target),
            details_json=details,
        )
    )


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _password_error(password: str) -> None:
    message = validate_new_password(password)
    if message is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=message)


def _pending_link(db: Session, user_id: str, now: datetime) -> Optional[PasswordLink]:
    return (
        db.query(PasswordLink)
        .filter(
            PasswordLink.user_id == user_id,
            PasswordLink.used_at.is_(None),
            PasswordLink.revoked_at.is_(None),
            PasswordLink.expires_at > now,
        )
        .order_by(PasswordLink.created_at.desc())
        .first()
    )


def _active_session_count(db: Session, user_id: str, now: datetime) -> int:
    return (
        db.query(func.count(UserSession.id))
        .filter(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
            (UserSession.channel != "browser") | (UserSession.last_seen_at > now - BROWSER_IDLE_LIFETIME),
        )
        .scalar()
        or 0
    )


def _account_response(db: Session, user: User, now: Optional[datetime] = None) -> AccountResponse:
    now = now or _now()
    link = _pending_link(db, str(user.id), now) if user.is_active else None
    return AccountResponse(
        id=str(user.id),
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=bool(user.is_active),
        must_change_password=bool(user.must_change_password),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        active_sessions=_active_session_count(db, str(user.id), now),
        password_link=(
            PasswordLinkState(status="pending", purpose=link.purpose, expires_at=link.expires_at)
            if link is not None
            else PasswordLinkState(status="none")
        ),
    )


def _get_account(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return user


def _revoke_pending_links(db: Session, user_id: str, now: datetime) -> None:
    db.execute(
        update(PasswordLink)
        .where(
            PasswordLink.user_id == user_id,
            PasswordLink.used_at.is_(None),
            PasswordLink.revoked_at.is_(None),
        )
        .values(revoked_at=now)
        .execution_options(synchronize_session=False)
    )


def _issue_link(db: Session, user: User, actor: User, purpose: str, now: datetime) -> IssuedPasswordLink:
    """Revoke older unused links of the account and create a new one; returns the URL once."""
    _revoke_pending_links(db, str(user.id), now)
    token = generate_opaque_secret()
    link = PasswordLink(
        user_id=str(user.id),
        token_hash=hash_opaque_secret(token),
        purpose=purpose,
        created_by_user_id=str(actor.id),
        created_at=now,
        expires_at=now + PASSWORD_LINK_LIFETIME,
    )
    db.add(link)
    _audit(db, actor, user, "password_link_created", {"purpose": purpose})
    return IssuedPasswordLink(
        url=f"{settings.public_origin.rstrip('/')}/set-password/{token}",
        purpose=purpose,
        expires_at=link.expires_at,
    )


def _lock_admin_set(db: Session) -> None:
    """Serialise changes that could remove the last active admin (TOCTOU-safe on PostgreSQL)."""
    if db.get_bind().dialect.name == "postgresql":
        key = int.from_bytes(hashlib.sha256(b"ardor-active-admins").digest()[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def _other_active_admins(db: Session, user_id: str) -> int:
    return (
        db.query(func.count(User.id))
        .filter(User.role == "admin", User.is_active == True, User.id != user_id)  # noqa: E712
        .scalar()
        or 0
    )


@router.get("/users", response_model=List[AccountResponse])
def list_accounts(
    actor: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """All accounts, including deactivated ones, newest first (admin only)."""
    now = _now()
    users = db.query(User).order_by(User.is_active.desc(), User.created_at.desc()).all()
    return [_account_response(db, user, now) for user in users]


@router.post("/users", response_model=AccountCreateResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    req: AccountCreateRequest,
    actor: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Create an account with an admin-chosen password or a one-time set-password link."""
    username = req.username.strip()
    if not USERNAME_PATTERN.fullmatch(username):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Username must be 3-32 characters: letters, digits, dot, dash or underscore.",
        )
    if db.query(User.id).filter(func.lower(User.username) == username.lower()).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already taken")
    email = _clean_optional(req.email)
    if email is not None and db.query(User.id).filter(func.lower(User.email) == email.lower()).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already in use")

    now = _now()
    manual = req.password is not None
    if manual:
        _password_error(req.password)
    user = User(
        username=username,
        full_name=req.full_name.strip(),
        email=email,
        role=req.role,
        is_active=True,
        created_at=now,
        # Without a manual password the account gets an unknown random password and
        # can only be entered after its owner sets one through the link.
        hashed_password=hash_password(req.password if manual else generate_opaque_secret()),
        must_change_password=bool(manual and req.require_password_change),
    )
    db.add(user)
    db.flush()
    _audit(db, actor, user, "account_created", {
        "username": username,
        "role": req.role,
        "password_mode": "manual" if manual else "link",
        "require_password_change": bool(manual and req.require_password_change),
    })
    issued = None if manual else _issue_link(db, user, actor, "invite", now)
    commit_auth_changes(db)
    db.refresh(user)
    return AccountCreateResponse(account=_account_response(db, user), password_link=issued)


@router.patch("/users/{user_id}", response_model=AccountResponse)
def update_account(
    user_id: str,
    req: AccountUpdateRequest,
    actor: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Change name, email, role or active state. Role change or deactivation revokes all sessions."""
    user = _get_account(db, user_id)
    now = _now()
    changes: dict = {}

    removes_admin = user.role == "admin" and user.is_active and (
        (req.role is not None and req.role != "admin") or req.is_active is False
    )
    if str(user.id) == str(actor.id) and removes_admin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot deactivate yourself or remove your own admin role.",
        )
    if removes_admin:
        _lock_admin_set(db)
        if _other_active_admins(db, str(user.id)) == 0:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The last active admin cannot be deactivated or demoted.",
            )

    if req.full_name is not None and req.full_name.strip() != (user.full_name or ""):
        changes["full_name"] = True
        user.full_name = req.full_name.strip()
    if "email" in req.model_fields_set:
        email = _clean_optional(req.email)
        if email != user.email:
            if email is not None and db.query(User.id).filter(
                func.lower(User.email) == email.lower(), User.id != user.id
            ).first() is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already in use")
            changes["email"] = True
            user.email = email
    revoke_reason = None
    if req.role is not None and req.role != user.role:
        changes["role"] = {"from": user.role, "to": req.role}
        user.role = req.role
        revoke_reason = RevocationReason.ROLE_CHANGED
    if req.is_active is not None and req.is_active != bool(user.is_active):
        changes["is_active"] = req.is_active
        user.is_active = req.is_active
        if not req.is_active:
            revoke_reason = RevocationReason.DEACTIVATED
            _revoke_pending_links(db, str(user.id), now)

    if changes:
        if revoke_reason is not None:
            revoke_all_sessions(db, str(user.id), revoke_reason, now=now)
        _audit(db, actor, user, "account_updated", {"changes": changes})
        commit_auth_changes(db)
        db.refresh(user)
    return _account_response(db, user, now)


@router.post("/users/{user_id}/password-link", response_model=IssuedPasswordLink)
def create_password_link(
    user_id: str,
    actor: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """New one-time link to set a password; older unused links of this account stop working."""
    user = _get_account(db, user_id)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Activate the account first")
    issued = _issue_link(db, user, actor, "invite" if user.last_login_at is None else "reset", _now())
    commit_auth_changes(db)
    return issued


@router.put("/users/{user_id}/password", response_model=AccountResponse)
def set_account_password(
    user_id: str,
    req: AdminSetPasswordRequest,
    actor: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Admin sets a password directly; every session and unused link of the account is revoked."""
    user = _get_account(db, user_id)
    _password_error(req.password)
    now = _now()
    user.hashed_password = hash_password(req.password)
    # Own password: no forced change; another account: as the admin chose.
    user.must_change_password = bool(req.require_password_change) and str(user.id) != str(actor.id)
    revoke_all_sessions(db, str(user.id), RevocationReason.ADMIN_REVOKE, now=now)
    _revoke_pending_links(db, str(user.id), now)
    _audit(db, actor, user, "account_password_set", {"require_password_change": user.must_change_password})
    commit_auth_changes(db)
    db.refresh(user)
    return _account_response(db, user, now)


def _usable_link(db: Session, token: str) -> tuple[PasswordLink, User]:
    """Unknown, used, revoked, expired and deactivated-account links are indistinguishable."""
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link is invalid or has expired")
    if not token or len(token) > 128:
        raise not_found
    link = db.query(PasswordLink).filter(PasswordLink.token_hash == hash_opaque_secret(token)).first()
    if link is None or link.used_at is not None or link.revoked_at is not None or _as_utc(link.expires_at) <= _now():
        raise not_found
    user = db.get(User, link.user_id)
    if user is None or not user.is_active:
        raise not_found
    return link, user


@router.get("/password-links/{token}", response_model=PasswordLinkInfo)
def get_password_link(token: str, db: Session = Depends(get_db)):
    """Public: show whose password the link sets, so the person knows it is theirs."""
    link, user = _usable_link(db, token)
    return PasswordLinkInfo(
        username=user.username,
        full_name=user.full_name,
        purpose=link.purpose,
        expires_at=link.expires_at,
    )


@router.post("/password-links/{token}", response_model=PasswordLinkUseResponse)
def use_password_link(token: str, req: PasswordLinkUseRequest, db: Session = Depends(get_db)):
    """Public: set the new password, burn the link and sign out every existing session."""
    link, user = _usable_link(db, token)
    _password_error(req.new_password)
    now = _now()
    # Conditional update: two concurrent submissions of the same link cannot both win.
    claimed = db.execute(
        update(PasswordLink)
        .where(PasswordLink.id == link.id, PasswordLink.used_at.is_(None), PasswordLink.revoked_at.is_(None))
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    ).rowcount
    if claimed != 1:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link is invalid or has expired")
    user.hashed_password = hash_password(req.new_password)
    user.must_change_password = False
    _revoke_pending_links(db, str(user.id), now)
    revoke_all_sessions(db, str(user.id), RevocationReason.PASSWORD_CHANGE, now=now)
    _audit(db, None, user, "password_link_used", {"purpose": link.purpose})
    commit_auth_changes(db)
    return PasswordLinkUseResponse(status="ok", username=user.username)
