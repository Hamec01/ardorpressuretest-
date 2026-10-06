"""Admin account management and one-time password links (docs/ACCESS_PLAN_R4-R7.md stage 1)."""

import os
from datetime import datetime, timedelta, timezone

_db_url = os.environ.get("DATABASE_URL", "")
_storage_dir = os.environ.get("STORAGE_DIR", "")

if not _db_url or "5432" in _db_url or "postgres" in _db_url.lower() or "ardor_pressure_test" in _db_url:
    raise RuntimeError("Use an isolated SQLite DATABASE_URL for this test module.")
if not _storage_dir or os.path.normpath(_storage_dir) == "/data/storage":
    raise RuntimeError("Use isolated test storage for this test module.")

import pytest
from fastapi.testclient import TestClient

from services.api.auth import hash_password, verify_password
from services.api.config import settings
from services.api.database import Base, SessionLocal, engine
from services.api.main import app
from services.api.models import AuditEvent, PasswordLink, User, UserSession
from services.api.session_service import create_browser_session, create_desktop_session

ADMIN_PASSWORD = "admin password 1"


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _create_user(username="boss", password=ADMIN_PASSWORD, *, role="admin", is_active=True):
    with SessionLocal() as db:
        user = User(
            username=username,
            full_name=username.title(),
            hashed_password=hash_password(password),
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        return user.id


def _login(client, username="boss", password=ADMIN_PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": settings.public_origin, "X-Ardor-Session-Mode": "browser"},
    )


def _unsafe(client):
    return {"Origin": settings.public_origin, "X-CSRF-Token": client.cookies.get(settings.csrf_cookie_name)}


def _admin_client():
    client = TestClient(app)
    client.__enter__()
    assert _login(client).status_code == 200
    return client


def _token_from(url: str) -> str:
    assert url.startswith(f"{settings.public_origin.rstrip('/')}/set-password/")
    return url.rsplit("/", 1)[1]


def test_only_admin_can_list_and_manage_accounts():
    _create_user()
    _create_user("fore", "fore password", role="foreman")
    with TestClient(app) as client:
        assert client.get("/api/v1/auth/users").status_code == 401
        assert _login(client, "fore", "fore password").status_code == 200
        assert client.get("/api/v1/auth/users").status_code == 403
        response = client.post(
            "/api/v1/auth/users",
            json={"username": "x-user", "full_name": "X", "role": "viewer"},
            headers=_unsafe(client),
        )
        assert response.status_code == 403


def test_list_shows_all_accounts_including_deactivated():
    _create_user()
    _create_user("gone", "gone password", role="viewer", is_active=False)
    client = _admin_client()
    rows = client.get("/api/v1/auth/users").json()
    assert {row["username"]: row["is_active"] for row in rows} == {"boss": True, "gone": False}
    assert all("hashed_password" not in row for row in rows)


def test_create_with_link_then_owner_sets_password_once():
    _create_user()
    client = _admin_client()
    response = client.post(
        "/api/v1/auth/users",
        json={"username": "Ivan.P", "full_name": " Ivan Petrov ", "role": "foreman"},
        headers=_unsafe(client),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["account"]["role"] == "foreman"
    assert body["account"]["full_name"] == "Ivan Petrov"
    assert body["account"]["password_link"]["status"] == "pending"
    token = _token_from(body["password_link"]["url"])

    with SessionLocal() as db:
        assert db.query(PasswordLink).one().token_hash != token  # only the hash is stored
        audit_text = str([e.details_json for e in db.query(AuditEvent).all()])
        assert token not in audit_text

    public = TestClient(app)
    assert _login(public, "Ivan.P", "anything").status_code == 401  # no usable password yet
    info = public.get(f"/api/v1/auth/password-links/{token}")
    assert info.status_code == 200 and info.json()["username"] == "Ivan.P"
    assert public.post(f"/api/v1/auth/password-links/{token}", json={"new_password": "12345"}).status_code == 422
    assert public.post(f"/api/v1/auth/password-links/{token}", json={"new_password": "abcdef"}).status_code == 200
    # one-time
    assert public.get(f"/api/v1/auth/password-links/{token}").status_code == 404
    assert public.post(f"/api/v1/auth/password-links/{token}", json={"new_password": "other1"}).status_code == 404
    login = _login(public, "Ivan.P", "abcdef")
    assert login.status_code == 200
    assert login.json()["user"]["must_change_password"] is False


def test_any_six_characters_are_a_valid_password():
    _create_user()
    client = _admin_client()
    response = client.post(
        "/api/v1/auth/users",
        json={"username": "simple", "full_name": "Simple", "role": "viewer",
              "password": "aaaaaa", "require_password_change": False},
        headers=_unsafe(client),
    )
    assert response.status_code == 201
    assert response.json()["password_link"] is None
    assert _login(TestClient(app), "simple", "aaaaaa").status_code == 200


def test_manual_password_can_require_change_on_first_login():
    _create_user()
    client = _admin_client()
    client.post(
        "/api/v1/auth/users",
        json={"username": "temp", "full_name": "Temp", "role": "viewer", "password": "start123"},
        headers=_unsafe(client),
    )
    login = _login(TestClient(app), "temp", "start123")
    assert login.status_code == 200
    assert login.json()["user"]["must_change_password"] is True


def test_duplicate_or_invalid_username_is_rejected():
    _create_user()
    client = _admin_client()
    payload = {"full_name": "Dup", "role": "viewer", "password": "secret1"}
    assert client.post("/api/v1/auth/users", json={**payload, "username": "BOSS"}, headers=_unsafe(client)).status_code == 409
    assert client.post("/api/v1/auth/users", json={**payload, "username": "a b"}, headers=_unsafe(client)).status_code == 422
    assert client.post("/api/v1/auth/users", json={**payload, "username": "ok", "role": "operator"}, headers=_unsafe(client)).status_code == 422


def test_new_link_revokes_previous_link_and_reset_signs_out_everywhere():
    _create_user()
    worker_id = _create_user("worker", "old password", role="viewer")
    with SessionLocal() as db:
        create_browser_session(db, worker_id, device_label="phone")
        create_desktop_session(db, worker_id, device_label="pc")
        db.commit()
    client = _admin_client()
    first = client.post(f"/api/v1/auth/users/{worker_id}/password-link", headers=_unsafe(client)).json()
    second = client.post(f"/api/v1/auth/users/{worker_id}/password-link", headers=_unsafe(client)).json()
    public = TestClient(app)
    assert public.get(f"/api/v1/auth/password-links/{_token_from(first['url'])}").status_code == 404
    assert public.post(f"/api/v1/auth/password-links/{_token_from(second['url'])}", json={"new_password": "new password"}).status_code == 200
    with SessionLocal() as db:
        assert db.query(UserSession).filter(UserSession.user_id == worker_id, UserSession.revoked_at.is_(None)).count() == 0
    assert _login(public, "worker", "old password").status_code == 401
    assert _login(public, "worker", "new password").status_code == 200


def test_expired_link_does_not_work():
    _create_user()
    worker_id = _create_user("worker", "old password", role="viewer")
    client = _admin_client()
    url = client.post(f"/api/v1/auth/users/{worker_id}/password-link", headers=_unsafe(client)).json()["url"]
    with SessionLocal() as db:
        link = db.query(PasswordLink).one()
        link.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    assert TestClient(app).get(f"/api/v1/auth/password-links/{_token_from(url)}").status_code == 404


def test_role_change_and_deactivation_revoke_sessions_and_links():
    _create_user()
    worker_id = _create_user("worker", "worker password", role="viewer")
    with SessionLocal() as db:
        create_browser_session(db, worker_id, device_label="phone")
        db.commit()
    client = _admin_client()
    response = client.patch(f"/api/v1/auth/users/{worker_id}", json={"role": "foreman"}, headers=_unsafe(client))
    assert response.status_code == 200 and response.json()["role"] == "foreman"
    with SessionLocal() as db:
        session = db.query(UserSession).filter(UserSession.user_id == worker_id).one()
        assert session.revoked_reason == "role_changed"

    url = client.post(f"/api/v1/auth/users/{worker_id}/password-link", headers=_unsafe(client)).json()["url"]
    response = client.patch(f"/api/v1/auth/users/{worker_id}", json={"is_active": False}, headers=_unsafe(client))
    assert response.status_code == 200 and response.json()["is_active"] is False
    assert TestClient(app).get(f"/api/v1/auth/password-links/{_token_from(url)}").status_code == 404
    assert _login(TestClient(app), "worker", "worker password").status_code == 401
    assert client.post(f"/api/v1/auth/users/{worker_id}/password-link", headers=_unsafe(client)).status_code == 409

    response = client.patch(f"/api/v1/auth/users/{worker_id}", json={"is_active": True}, headers=_unsafe(client))
    assert response.json()["is_active"] is True
    assert _login(TestClient(app), "worker", "worker password").status_code == 200


def test_last_admin_and_self_protection():
    boss_id = _create_user()
    client = _admin_client()
    assert client.patch(f"/api/v1/auth/users/{boss_id}", json={"is_active": False}, headers=_unsafe(client)).status_code == 409
    assert client.patch(f"/api/v1/auth/users/{boss_id}", json={"role": "viewer"}, headers=_unsafe(client)).status_code == 409

    other_admin = _create_user("second", "second password", role="admin")
    # another admin may be demoted while one active admin remains
    assert client.patch(f"/api/v1/auth/users/{other_admin}", json={"role": "viewer"}, headers=_unsafe(client)).status_code == 200
    with SessionLocal() as db:
        assert db.query(User).filter(User.role == "admin", User.is_active == True).count() == 1  # noqa: E712


def test_admin_sets_password_directly_and_old_password_stops_working():
    _create_user()
    worker_id = _create_user("worker", "worker password", role="viewer")
    client = _admin_client()
    response = client.put(
        f"/api/v1/auth/users/{worker_id}/password",
        json={"password": "fresh1", "require_password_change": True},
        headers=_unsafe(client),
    )
    assert response.status_code == 200 and response.json()["must_change_password"] is True
    with SessionLocal() as db:
        assert verify_password("fresh1", db.get(User, worker_id).hashed_password)
    assert _login(TestClient(app), "worker", "worker password").status_code == 401


def test_admin_mutations_require_csrf():
    worker_id = _create_user("worker", "worker password", role="viewer")
    _create_user()
    client = _admin_client()
    response = client.patch(f"/api/v1/auth/users/{worker_id}", json={"role": "foreman"}, headers={"Origin": settings.public_origin})
    assert response.status_code in (401, 403)
