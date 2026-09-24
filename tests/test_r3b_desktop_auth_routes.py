"""R3 native desktop login and mandatory refresh-rotation route tests."""

import hashlib
import os

_db_url = os.environ.get("DATABASE_URL", "")
_storage_dir = os.environ.get("STORAGE_DIR", "")

if not _db_url or "5432" in _db_url or "postgres" in _db_url.lower() or "ardor_pressure_test" in _db_url:
    raise RuntimeError("Use an isolated SQLite DATABASE_URL for this test module.")
if not _storage_dir or os.path.normpath(_storage_dir) == "/data/storage":
    raise RuntimeError("Use isolated test storage for this test module.")

import pytest
from fastapi.testclient import TestClient

from services.api.auth import hash_password, verify_desktop_access_token, verify_password
from services.api.config import settings
from services.api.database import Base, SessionLocal, engine
from services.api.main import app
from services.api.models import AuditEvent, User, UserSession
from services.api.security import hash_opaque_secret


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _create_user(*, hashed_password=None):
    with SessionLocal() as db:
        user = User(
            username="desktop-user",
            full_name="Desktop User",
            hashed_password=hashed_password or hash_password("desktop password"),
            role="viewer",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


def _login(client, password="desktop password", device_label="Field laptop"):
    return client.post(
        "/api/v1/desktop/login",
        json={
            "username": "desktop-user",
            "password": password,
            "device_label": device_label,
        },
    )


def _legacy_hash(password, salt="desktop-legacy-salt"):
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
    ).hex()
    return f"{salt}${digest}"


def test_desktop_login_issues_session_bound_access_and_hash_only_refresh():
    user_id = _create_user()
    with TestClient(app) as client:
        response = _login(client)
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 900
        assert body["user"]["id"] == user_id
        assert client.cookies.get(settings.session_cookie_name) is None
        assert client.cookies.get(settings.csrf_cookie_name) is None

        access = verify_desktop_access_token(body["access_token"])
        assert access.ok is True
        assert access.user_id == user_id
        assert access.session_id
        assert client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        ).status_code == 200

    with SessionLocal() as db:
        session = db.query(UserSession).one()
        assert session.id == access.session_id
        assert session.channel == "desktop"
        assert session.device_label == "Field laptop"
        assert session.token_hash == hash_opaque_secret(body["refresh_token"])
        assert body["refresh_token"] not in session.token_hash
        assert session.previous_token_hash is None
        assert session.csrf_token_hash is None
        assert db.query(AuditEvent).filter(AuditEvent.action == "login").count() == 1


def test_refresh_rotates_secret_and_returns_new_session_bound_access_token():
    user_id = _create_user()
    with TestClient(app) as client:
        login = _login(client).json()
        old_refresh = login["refresh_token"]
        old_access = verify_desktop_access_token(login["access_token"])
        response = client.post(
            "/api/v1/desktop/token/refresh",
            json={"refresh_token": old_refresh},
        )
        assert response.status_code == 200
        refreshed = response.json()
        assert refreshed["refresh_token"] != old_refresh
        access = verify_desktop_access_token(refreshed["access_token"])
        assert access.ok is True
        assert access.user_id == user_id
        assert access.session_id == old_access.session_id

    with SessionLocal() as db:
        session = db.get(UserSession, access.session_id)
        assert session.token_hash == hash_opaque_secret(refreshed["refresh_token"])
        assert session.previous_token_hash == hash_opaque_secret(old_refresh)
        assert session.revoked_at is None


def test_replaying_rotated_refresh_revokes_session_and_invalidates_access_immediately():
    _create_user()
    with TestClient(app) as client:
        login = _login(client).json()
        old_refresh = login["refresh_token"]
        refreshed = client.post(
            "/api/v1/desktop/token/refresh", json={"refresh_token": old_refresh}
        ).json()
        replay = client.post(
            "/api/v1/desktop/token/refresh", json={"refresh_token": old_refresh}
        )
        assert replay.status_code == 401
        assert replay.json() == {"detail": "Refresh token invalid or expired"}
        assert client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {refreshed['access_token']}"},
        ).status_code == 401
        assert client.post(
            "/api/v1/desktop/token/refresh",
            json={"refresh_token": refreshed["refresh_token"]},
        ).status_code == 401

    with SessionLocal() as db:
        session = db.query(UserSession).one()
        assert session.revoked_reason == "reuse_detected"
        assert (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "desktop_refresh_reuse_detected")
            .count()
            == 1
        )


@pytest.mark.parametrize(
    "bad_refresh",
    [
        "header.payload.signature",
        "not-a-valid-refresh",
        "A" * 42,
        "A" * 44,
    ],
)
def test_refresh_rejects_jwt_shaped_or_malformed_values_without_mutation(bad_refresh):
    _create_user()
    with TestClient(app) as client:
        login = _login(client).json()
        response = client.post(
            "/api/v1/desktop/token/refresh",
            json={"refresh_token": bad_refresh},
        )
        assert response.status_code == 401
    with SessionLocal() as db:
        session = db.query(UserSession).one()
        assert session.token_hash == hash_opaque_secret(login["refresh_token"])
        assert session.previous_token_hash is None
        assert session.revoked_at is None


def test_desktop_login_upgrades_legacy_password_and_preserves_spaces():
    password = " desktop legacy pass ☃ "
    user_id = _create_user(hashed_password=_legacy_hash(password))
    with TestClient(app) as client:
        assert _login(client, password=password).status_code == 200
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.hashed_password.startswith("$argon2id$")
        assert verify_password(password, user.hashed_password) is True
        assert verify_password(password.strip(), user.hashed_password) is False
        assert user.last_login_at is not None


def test_inactive_user_cannot_refresh_and_session_is_revoked():
    user_id = _create_user()
    with TestClient(app) as client:
        login = _login(client).json()
        with SessionLocal() as db:
            user = db.get(User, user_id)
            user.is_active = False
            db.commit()
        response = client.post(
            "/api/v1/desktop/token/refresh",
            json={"refresh_token": login["refresh_token"]},
        )
        assert response.status_code == 401
    with SessionLocal() as db:
        session = db.query(UserSession).one()
        assert session.revoked_reason == "deactivated"


def test_desktop_logout_revokes_backing_session_and_old_access_stops_working():
    _create_user()
    with TestClient(app) as client:
        login = _login(client).json()
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    with SessionLocal() as db:
        assert db.query(UserSession).one().revoked_reason == "logout"


def test_desktop_login_never_requires_or_sets_browser_origin_or_cookies():
    _create_user()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/desktop/login",
            json={"username": "desktop-user", "password": "desktop password"},
            headers={"Origin": "https://untrusted.example"},
        )
        assert response.status_code == 200
        assert "set-cookie" not in response.headers
