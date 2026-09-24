"""R3 multi-scheme authentication context tests on private in-memory SQLite."""

import os

_db_url = os.environ.get("DATABASE_URL", "")
_storage_dir = os.environ.get("STORAGE_DIR", "")

if not _db_url or "5432" in _db_url or "postgres" in _db_url.lower() or "ardor_pressure_test" in _db_url:
    raise RuntimeError("Use an isolated SQLite DATABASE_URL for this test module.")
if not _storage_dir or os.path.normpath(_storage_dir) == "/data/storage":
    raise RuntimeError("Use isolated test storage for this test module.")

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from services.api.auth import (
    AuthenticationMethod,
    authenticate_request,
    create_access_token,
    create_desktop_access_token,
    hash_password,
    require_authenticated_user,
    require_role,
)
from services.api.config import settings
from services.api.database import Base
from services.api.models import User
from services.api.session_service import (
    RevocationReason,
    create_browser_session,
    create_desktop_session,
    revoke_session,
)


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
def viewer(db_session):
    user = User(
        username="viewer-user",
        hashed_password=hash_password("viewer-password"),
        role="viewer",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _bearer(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _request(
    path="/api/v1/auth/me",
    cookie_value=None,
    *,
    method="GET",
    csrf_value=None,
    origin=None,
):
    headers = []
    if cookie_value is not None:
        cookies = [f"{settings.session_cookie_name}={cookie_value}"]
        if csrf_value is not None:
            cookies.append(f"{settings.csrf_cookie_name}={csrf_value}")
        headers.append((b"cookie", "; ".join(cookies).encode("ascii")))
    if csrf_value is not None:
        headers.append((b"x-csrf-token", csrf_value.encode("ascii")))
    if origin is not None:
        headers.append((b"origin", origin.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": headers,
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
        }
    )


def test_legacy_bearer_remains_accepted(db_session, viewer):
    token = create_access_token({"sub": viewer.id})
    context = authenticate_request(db_session, auth=_bearer(token))
    assert context.user.id == viewer.id
    assert context.method is AuthenticationMethod.LEGACY_BEARER
    assert context.session_id is None


def test_browser_cookie_authenticates_without_bearer(db_session, viewer):
    issued = create_browser_session(db_session, viewer.id)
    db_session.commit()
    context = authenticate_request(
        db_session,
        request=_request(cookie_value=issued.session_secret),
    )
    assert context.user.id == viewer.id
    assert context.method is AuthenticationMethod.BROWSER_SESSION
    assert context.session_id == issued.session_id


def test_invalid_present_cookie_never_falls_back_to_valid_bearer(db_session, viewer):
    token = create_access_token({"sub": viewer.id})
    with pytest.raises(HTTPException) as exc_info:
        authenticate_request(
            db_session,
            request=_request(cookie_value="A" * 43),
            auth=_bearer(token),
        )
    assert exc_info.value.status_code == 401


def test_desktop_access_requires_matching_live_desktop_session(db_session, viewer):
    issued = create_desktop_session(db_session, viewer.id)
    db_session.commit()
    token = create_desktop_access_token(viewer.id, issued.session_id)
    context = authenticate_request(db_session, auth=_bearer(token))
    assert context.user.id == viewer.id
    assert context.method is AuthenticationMethod.DESKTOP_ACCESS
    assert context.session_id == issued.session_id


def test_desktop_access_rejected_after_session_revocation(db_session, viewer):
    issued = create_desktop_session(db_session, viewer.id)
    db_session.commit()
    token = create_desktop_access_token(viewer.id, issued.session_id)
    revoke_session(
        db_session,
        viewer.id,
        issued.session_id,
        RevocationReason.LOGOUT,
        now=datetime.now(timezone.utc),
    )
    db_session.commit()
    with pytest.raises(HTTPException) as exc_info:
        authenticate_request(db_session, auth=_bearer(token))
    assert exc_info.value.status_code == 401


def test_desktop_token_user_must_match_session_owner(db_session, viewer):
    issued = create_desktop_session(db_session, viewer.id)
    db_session.commit()
    token = create_desktop_access_token("different-user", issued.session_id)
    with pytest.raises(HTTPException) as exc_info:
        authenticate_request(db_session, auth=_bearer(token))
    assert exc_info.value.status_code == 401


def test_typed_or_session_bound_token_never_falls_back_to_legacy(db_session, viewer):
    typed = create_access_token({"sub": viewer.id, "typ": "unknown"})
    bound = create_access_token({"sub": viewer.id, "sid": "missing-session"})
    for token in (typed, bound):
        with pytest.raises(HTTPException) as exc_info:
            authenticate_request(db_session, auth=_bearer(token))
        assert exc_info.value.status_code == 401


def test_viewer_is_accepted_by_transitional_authenticated_user_dependency(db_session, viewer):
    token = create_access_token({"sub": viewer.id})
    result = require_authenticated_user(auth=_bearer(token), db=db_session, request=None)
    assert result.id == viewer.id


def test_require_role_blocks_must_change_password_user(db_session, viewer):
    viewer.must_change_password = True
    db_session.commit()
    token = create_access_token({"sub": viewer.id})
    checker = require_role(["viewer"])
    with pytest.raises(HTTPException) as exc_info:
        checker(auth=_bearer(token), db=db_session, request=None)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Password change required"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/auth/me",
        "/api/v1/auth/logout",
        "/api/v1/auth/change-password",
    ],
)
def test_must_change_password_allowlist_is_exact(db_session, viewer, path):
    viewer.must_change_password = True
    db_session.commit()
    token = create_access_token({"sub": viewer.id})
    checker = require_role(["viewer"])
    result = checker(auth=_bearer(token), db=db_session, request=_request(path=path))
    assert result.id == viewer.id


def test_must_change_password_similar_path_is_not_allowed(db_session, viewer):
    viewer.must_change_password = True
    db_session.commit()
    token = create_access_token({"sub": viewer.id})
    checker = require_role(["viewer"])
    with pytest.raises(HTTPException) as exc_info:
        checker(
            auth=_bearer(token),
            db=db_session,
            request=_request(path="/api/v1/auth/me/extra"),
        )
    assert exc_info.value.status_code == 403


def test_non_object_legacy_payload_fails_as_401_not_500(db_session):
    import base64
    import hashlib
    import hmac

    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(b'[]').decode().rstrip("=")
    message = f"{header}.{payload}"
    signature = base64.urlsafe_b64encode(
        hmac.new(settings.secret_key.encode(), message.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")
    with pytest.raises(HTTPException) as exc_info:
        authenticate_request(db_session, auth=_bearer(f"{message}.{signature}"))
    assert exc_info.value.status_code == 401


def test_browser_last_seen_commit_failure_rolls_back_and_returns_503(
    db_session, viewer, monkeypatch
):
    from datetime import timedelta

    issued = create_browser_session(
        db_session,
        viewer.id,
        now=datetime.now(timezone.utc) - timedelta(minutes=6),
    )
    db_session.commit()
    rollback_called = False

    def fail_commit():
        raise RuntimeError("sensitive database failure")

    original_rollback = db_session.rollback

    def track_rollback():
        nonlocal rollback_called
        rollback_called = True
        original_rollback()

    monkeypatch.setattr(db_session, "commit", fail_commit)
    monkeypatch.setattr(db_session, "rollback", track_rollback)
    with pytest.raises(HTTPException) as exc_info:
        authenticate_request(
            db_session,
            request=_request(cookie_value=issued.session_secret),
        )
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Session update failed"
    assert rollback_called is True


def test_missing_credentials_remain_fail_closed(db_session, viewer):
    with pytest.raises(HTTPException) as exc_info:
        authenticate_request(db_session)
    assert exc_info.value.status_code == 401


def test_require_role_enforces_csrf_for_every_cookie_authenticated_unsafe_method(
    db_session, viewer
):
    issued = create_browser_session(db_session, viewer.id)
    db_session.commit()
    checker = require_role(["viewer"])

    with pytest.raises(HTTPException) as exc_info:
        checker(
            auth=None,
            db=db_session,
            request=_request(
                path="/api/v1/business-mutation",
                method="PATCH",
                cookie_value=issued.session_secret,
            ),
        )
    assert exc_info.value.status_code == 403

    authenticated = checker(
        auth=None,
        db=db_session,
        request=_request(
            path="/api/v1/business-mutation",
            method="PATCH",
            cookie_value=issued.session_secret,
            csrf_value=issued.csrf_secret,
            origin=settings.public_origin,
        ),
    )
    assert authenticated.id == viewer.id


def test_require_role_does_not_apply_browser_csrf_protocol_to_bearer_mutation(
    db_session, viewer
):
    checker = require_role(["viewer"])
    token = create_access_token({"sub": viewer.id})
    authenticated = checker(
        auth=_bearer(token),
        db=db_session,
        request=_request(path="/api/v1/business-mutation", method="POST"),
    )
    assert authenticated.id == viewer.id
