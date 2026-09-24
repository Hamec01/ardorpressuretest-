"""R3 browser login, cookie, CSRF, logout, and auth-route policy tests."""

import hashlib
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
from services.api.http_security import set_browser_auth_cookies
from services.api.main import app
from services.api.models import AuditEvent, User, UserSession
from services.api.security import hash_opaque_secret
from services.api.session_service import create_browser_session, create_desktop_session


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _create_user(
    username="viewer-one",
    password="correct horse battery staple",
    *,
    role="viewer",
    must_change_password=False,
    hashed_password=None,
):
    with SessionLocal() as db:
        user = User(
            username=username,
            full_name="Viewer One",
            hashed_password=hashed_password or hash_password(password),
            role=role,
            is_active=True,
            must_change_password=must_change_password,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


def _login(client, username="viewer-one", password="correct horse battery staple", *, origin=True):
    headers = {"Origin": settings.public_origin} if origin else {}
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers=headers,
    )


def _legacy_pbkdf2_hash(password, salt="legacy-salt"):
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
    ).hex()
    return f"{salt}${digest}"


def _replace_client_cookie(client, name, value):
    try:
        client.cookies.delete(name, domain="testserver.local", path="/")
    except KeyError:
        pass
    client.cookies.set(name, value, domain="testserver.local", path="/")


def test_trusted_origin_login_creates_hash_only_browser_session_and_both_cookies():
    user_id = _create_user()
    with TestClient(app) as client:
        response = _login(client)
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["id"] == user_id
        assert body["user"]["must_change_password"] is False
        assert body["access_token"]

        session_secret = client.cookies.get(settings.session_cookie_name)
        csrf_secret = client.cookies.get(settings.csrf_cookie_name)
        assert session_secret and csrf_secret
        assert session_secret not in response.text
        assert csrf_secret not in response.text

        set_cookie_headers = response.headers.get_list("set-cookie")
        session_header = next(h for h in set_cookie_headers if settings.session_cookie_name in h)
        csrf_header = next(h for h in set_cookie_headers if settings.csrf_cookie_name in h)
        assert "HttpOnly" in session_header
        assert "HttpOnly" not in csrf_header
        assert "SameSite=lax" in session_header
        assert "Path=/" in session_header
        assert "Domain=" not in session_header

    with SessionLocal() as db:
        rows = db.query(UserSession).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.user_id == user_id
        assert row.channel == "browser"
        assert row.token_hash == hash_opaque_secret(session_secret)
        assert row.csrf_token_hash == hash_opaque_secret(csrf_secret)
        assert session_secret not in row.token_hash
        assert csrf_secret not in row.csrf_token_hash
        assert db.query(AuditEvent).filter(AuditEvent.action == "login").count() == 1


def test_cookie_authenticates_me_and_must_change_password_is_visible():
    _create_user(must_change_password=True)
    with TestClient(app) as client:
        assert _login(client).status_code == 200
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert response.json()["username"] == "viewer-one"
        assert response.json()["must_change_password"] is True


def test_untrusted_or_absent_origin_gets_legacy_bearer_but_no_ambient_cookie():
    _create_user()
    for headers in ({}, {"Origin": "https://attacker.example"}):
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "viewer-one", "password": "correct horse battery staple"},
                headers=headers,
            )
            assert response.status_code == 200
            assert response.json()["access_token"]
            assert client.cookies.get(settings.session_cookie_name) is None
            assert client.cookies.get(settings.csrf_cookie_name) is None

    with SessionLocal() as db:
        assert db.query(UserSession).count() == 0
        assert db.query(AuditEvent).filter(AuditEvent.action == "login").count() == 2


def test_browser_logout_requires_matching_origin_and_server_bound_csrf():
    _create_user()
    with TestClient(app) as client:
        assert _login(client).status_code == 200
        csrf_secret = client.cookies.get(settings.csrf_cookie_name)

        missing = client.post("/api/v1/auth/logout")
        assert missing.status_code == 403
        _replace_client_cookie(client, settings.csrf_cookie_name, "A" * 43)
        wrong = client.post(
            "/api/v1/auth/logout",
            headers={"Origin": settings.public_origin, "X-CSRF-Token": "A" * 43},
        )
        assert wrong.status_code == 403

        _replace_client_cookie(client, settings.csrf_cookie_name, csrf_secret)

        ok = client.post(
            "/api/v1/auth/logout",
            headers={"Origin": settings.public_origin, "X-CSRF-Token": csrf_secret},
        )
        assert ok.status_code == 200
        assert ok.json() == {"status": "ok"}
        assert client.cookies.get(settings.session_cookie_name) is None
        assert client.cookies.get(settings.csrf_cookie_name) is None

    with SessionLocal() as db:
        session = db.query(UserSession).one()
        assert session.revoked_at is not None
        assert session.revoked_reason == "logout"
        assert db.query(AuditEvent).filter(AuditEvent.action == "logout").count() == 1


def test_invalid_browser_session_401_clears_both_stale_cookies():
    with TestClient(app) as client:
        _replace_client_cookie(client, settings.session_cookie_name, "A" * 43)
        _replace_client_cookie(client, settings.csrf_cookie_name, "B" * 43)
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert "x-ardor-clear-session" not in response.headers
        assert client.cookies.get(settings.session_cookie_name) is None
        assert client.cookies.get(settings.csrf_cookie_name) is None


def test_server_cookie_profile_uses_host_prefix_secure_path_and_no_domain(monkeypatch):
    from fastapi import Response

    monkeypatch.setattr(settings, "environment", "staging")
    response = Response()
    set_browser_auth_cookies(response, "A" * 43, "B" * 43)
    headers = response.headers.getlist("set-cookie")
    assert len(headers) == 2
    session_header = next(h for h in headers if "__Host-ardor_session=" in h)
    csrf_header = next(h for h in headers if "__Host-ardor_csrf=" in h)
    assert "Secure" in session_header
    assert "HttpOnly" in session_header
    assert "Secure" in csrf_header
    assert "HttpOnly" not in csrf_header
    assert "Path=/" in session_header
    assert "Domain=" not in session_header


def test_legacy_bearer_logout_is_honest_client_side_only_success():
    _create_user()
    with TestClient(app) as client:
        login = _login(client, origin=False)
        token = login.json()["access_token"]
        logout = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert logout.status_code == 200
        assert client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        ).status_code == 200
    with SessionLocal() as db:
        assert db.query(UserSession).count() == 0


def test_login_transparently_upgrades_legacy_password_in_same_success_path():
    password = " legacy unicode pass ☃ "
    user_id = _create_user(password=password, hashed_password=_legacy_pbkdf2_hash(password))
    with TestClient(app) as client:
        response = _login(client, password=password)
        assert response.status_code == 200
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.hashed_password.startswith("$argon2id$")
        assert verify_password(password, user.hashed_password) is True
        assert user.last_login_at is not None
        assert db.query(UserSession).count() == 1
        assert db.query(AuditEvent).filter(AuditEvent.action == "login").count() == 1


def test_unknown_user_runs_dummy_argon2_and_records_same_safe_401(monkeypatch):
    calls = []

    def tracked_verify(password, stored_hash):
        calls.append((password, stored_hash))
        return False

    monkeypatch.setattr("services.api.routes.auth.verify_password", tracked_verify)
    with TestClient(app) as client:
        response = _login(client, username="does-not-exist", password="not-the-password")
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}
    assert len(calls) == 1
    assert calls[0][0] == "not-the-password"
    assert calls[0][1].startswith("$argon2id$")
    with SessionLocal() as db:
        event = db.query(AuditEvent).filter(AuditEvent.action == "login_failed").one()
        assert event.user_id is None
        assert "not-the-password" not in str(event.details_json)


def test_users_endpoint_is_admin_only_for_bearer_and_cookie_sessions():
    _create_user()
    _create_user(username="admin-two", role="admin")

    with TestClient(app) as viewer_client:
        viewer_login = _login(viewer_client)
        assert viewer_login.status_code == 200
        assert viewer_client.get("/api/v1/auth/users").status_code == 403

    with TestClient(app) as admin_client:
        admin_login = _login(admin_client, username="admin-two")
        assert admin_login.status_code == 200
        users = admin_client.get("/api/v1/auth/users")
        assert users.status_code == 200
        assert {item["username"] for item in users.json()} == {"viewer-one", "admin-two"}


def test_wrong_password_never_creates_session_or_updates_last_login():
    user_id = _create_user()
    with TestClient(app) as client:
        response = _login(client, password="wrong-password")
        assert response.status_code == 401
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.last_login_at is None
        assert db.query(UserSession).count() == 0
        assert db.query(AuditEvent).filter(AuditEvent.action == "login_failed").count() == 1


def test_sixth_attempt_is_rate_limited_before_password_hash_work(monkeypatch):
    _create_user()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        for offset in range(5):
            db.add(
                AuditEvent(
                    entity_type="user",
                    entity_id="viewer-one",
                    action="login_failed",
                    actor_name="viewer-one",
                    details_json={},
                    created_at=now - timedelta(seconds=offset),
                )
            )
        db.commit()

    def password_work_must_not_run(*_args, **_kwargs):
        raise AssertionError("password hashing must not run after the rate-limit gate")

    monkeypatch.setattr(
        "services.api.routes.auth.check_password_with_upgrade",
        password_work_must_not_run,
    )
    with TestClient(app) as client:
        response = _login(client)
    assert response.status_code == 429
    assert response.json() == {"detail": "Too many login attempts. Try again later."}
    assert 1 <= int(response.headers["Retry-After"]) <= 900


def test_failures_outside_window_do_not_rate_limit(monkeypatch):
    _create_user()
    old = datetime.now(timezone.utc) - timedelta(minutes=16)
    with SessionLocal() as db:
        for offset in range(6):
            db.add(
                AuditEvent(
                    entity_type="user",
                    entity_id="viewer-one",
                    action="login_failed",
                    actor_name="viewer-one",
                    details_json={},
                    created_at=old - timedelta(seconds=offset),
                )
            )
        db.commit()
    with TestClient(app) as client:
        assert _login(client).status_code == 200


def test_change_password_rotates_current_browser_session_and_revokes_all_others():
    user_id = _create_user(must_change_password=True)
    old_password = "correct horse battery staple"
    new_password = " new unicode password ☃ "
    with TestClient(app) as client:
        assert _login(client).status_code == 200
        old_session_secret = client.cookies.get(settings.session_cookie_name)
        old_csrf_secret = client.cookies.get(settings.csrf_cookie_name)

        with SessionLocal() as db:
            current_id = db.query(UserSession).filter(UserSession.channel == "browser").one().id
            other_browser = create_browser_session(db, user_id, device_label="other browser")
            other_desktop = create_desktop_session(db, user_id, device_label="desktop")
            db.commit()

        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": old_password, "new_password": new_password},
            headers={"Origin": settings.public_origin, "X-CSRF-Token": old_csrf_secret},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "reauthentication_required": False}
        new_session_secret = client.cookies.get(settings.session_cookie_name)
        new_csrf_secret = client.cookies.get(settings.csrf_cookie_name)
        assert new_session_secret != old_session_secret
        assert new_csrf_secret != old_csrf_secret
        assert client.get("/api/v1/auth/me").status_code == 200

    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.must_change_password is False
        assert verify_password(new_password, user.hashed_password) is True
        assert verify_password(new_password.strip(), user.hashed_password) is False
        assert verify_password(old_password, user.hashed_password) is False

        current = db.get(UserSession, current_id)
        assert current.revoked_at is None
        assert current.token_hash == hash_opaque_secret(new_session_secret)
        assert current.csrf_token_hash == hash_opaque_secret(new_csrf_secret)
        assert current.token_hash != hash_opaque_secret(old_session_secret)
        assert db.get(UserSession, other_browser.session_id).revoked_reason == "password_change"
        assert db.get(UserSession, other_desktop.session_id).revoked_reason == "password_change"
        assert db.query(AuditEvent).filter(AuditEvent.action == "password_changed").count() == 1


@pytest.mark.parametrize("new_password", ["short", "x" * 129])
def test_change_password_rejects_invalid_new_length_without_mutation(new_password):
    user_id = _create_user()
    with TestClient(app) as client:
        assert _login(client).status_code == 200
        old_session_secret = client.cookies.get(settings.session_cookie_name)
        csrf_secret = client.cookies.get(settings.csrf_cookie_name)
        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "correct horse battery staple",
                "new_password": new_password,
            },
            headers={"Origin": settings.public_origin, "X-CSRF-Token": csrf_secret},
        )
        assert response.status_code == 422
        assert client.cookies.get(settings.session_cookie_name) == old_session_secret
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert verify_password("correct horse battery staple", user.hashed_password) is True
        assert db.query(AuditEvent).filter(AuditEvent.action == "password_changed").count() == 0


def test_change_password_rejects_wrong_current_password_without_mutation():
    user_id = _create_user(must_change_password=True)
    with TestClient(app) as client:
        assert _login(client).status_code == 200
        session_secret = client.cookies.get(settings.session_cookie_name)
        csrf_secret = client.cookies.get(settings.csrf_cookie_name)
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "wrong current", "new_password": "valid new password"},
            headers={"Origin": settings.public_origin, "X-CSRF-Token": csrf_secret},
        )
        assert response.status_code == 401
        assert client.cookies.get(settings.session_cookie_name) == session_secret
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.must_change_password is True
        assert verify_password("correct horse battery staple", user.hashed_password) is True
        assert db.query(UserSession).filter(UserSession.revoked_at.isnot(None)).count() == 0


def test_change_password_failure_rolls_back_password_flag_and_all_session_changes(monkeypatch):
    user_id = _create_user(must_change_password=True)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert _login(client).status_code == 200
        csrf_secret = client.cookies.get(settings.csrf_cookie_name)
        with SessionLocal() as db:
            other = create_desktop_session(db, user_id)
            db.commit()

        def fail_after_other_sessions_were_staged(*_args, **_kwargs):
            raise RuntimeError("injected failure after staged revocations")

        monkeypatch.setattr(
            "services.api.routes.auth.rotate_browser_session_secrets",
            fail_after_other_sessions_were_staged,
        )
        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "correct horse battery staple",
                "new_password": "valid replacement password",
            },
            headers={"Origin": settings.public_origin, "X-CSRF-Token": csrf_secret},
        )
        assert response.status_code == 500

    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.must_change_password is True
        assert verify_password("correct horse battery staple", user.hashed_password) is True
        assert verify_password("valid replacement password", user.hashed_password) is False
        assert db.get(UserSession, other.session_id).revoked_at is None
        assert db.query(AuditEvent).filter(AuditEvent.action == "password_changed").count() == 0


def test_sessions_list_contains_only_safe_fields_and_marks_current():
    user_id = _create_user()
    with TestClient(app) as client:
        assert _login(client).status_code == 200
        with SessionLocal() as db:
            create_desktop_session(db, user_id, device_label="field laptop")
            db.commit()
        response = client.get("/api/v1/auth/sessions")
        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) == 2
        assert sum(item["is_current"] for item in sessions) == 1
        assert {item["channel"] for item in sessions} == {"browser", "desktop"}
        assert any(item["device_label"] == "field laptop" for item in sessions)
        assert all("token_hash" not in item and "csrf_token_hash" not in item for item in sessions)


def test_sessions_list_is_blocked_until_required_password_change():
    _create_user(must_change_password=True)
    with TestClient(app) as client:
        assert _login(client).status_code == 200
        response = client.get("/api/v1/auth/sessions")
        assert response.status_code == 403
        assert response.json() == {"detail": "Password change required"}


def test_delete_owned_other_session_requires_csrf_and_revokes_only_target():
    user_id = _create_user()
    with TestClient(app) as client:
        assert _login(client).status_code == 200
        csrf_secret = client.cookies.get(settings.csrf_cookie_name)
        with SessionLocal() as db:
            current_id = db.query(UserSession).filter(UserSession.channel == "browser").one().id
            other = create_desktop_session(db, user_id, device_label="old laptop")
            db.commit()

        missing_csrf = client.delete(f"/api/v1/auth/sessions/{other.session_id}")
        assert missing_csrf.status_code == 403
        response = client.delete(
            f"/api/v1/auth/sessions/{other.session_id}",
            headers={"Origin": settings.public_origin, "X-CSRF-Token": csrf_secret},
        )
        assert response.status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 200

    with SessionLocal() as db:
        assert db.get(UserSession, current_id).revoked_at is None
        assert db.get(UserSession, other.session_id).revoked_at is not None


def test_delete_session_cannot_revoke_another_users_session():
    _create_user()
    other_user_id = _create_user(username="other-viewer")
    with SessionLocal() as db:
        other = create_desktop_session(db, other_user_id)
        db.commit()
    with TestClient(app) as client:
        assert _login(client).status_code == 200
        csrf_secret = client.cookies.get(settings.csrf_cookie_name)
        response = client.delete(
            f"/api/v1/auth/sessions/{other.session_id}",
            headers={"Origin": settings.public_origin, "X-CSRF-Token": csrf_secret},
        )
        assert response.status_code == 404
    with SessionLocal() as db:
        assert db.get(UserSession, other.session_id).revoked_at is None


def test_delete_current_browser_session_clears_cookies_and_invalidates_me():
    _create_user()
    with TestClient(app) as client:
        assert _login(client).status_code == 200
        csrf_secret = client.cookies.get(settings.csrf_cookie_name)
        sessions = client.get("/api/v1/auth/sessions").json()
        current_id = next(item["id"] for item in sessions if item["is_current"])
        response = client.delete(
            f"/api/v1/auth/sessions/{current_id}",
            headers={"Origin": settings.public_origin, "X-CSRF-Token": csrf_secret},
        )
        assert response.status_code == 200
        assert client.cookies.get(settings.session_cookie_name) is None
        assert client.cookies.get(settings.csrf_cookie_name) is None
        assert client.get("/api/v1/auth/me").status_code == 401
