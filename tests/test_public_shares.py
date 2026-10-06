"""Token share links and legacy /share/{log_no} compatibility (docs/ACCESS_PLAN_R4-R7.md stage 2)."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

_db_url = os.environ.get("DATABASE_URL", "")
_storage_dir = os.environ.get("STORAGE_DIR", "")

if not _db_url or "5432" in _db_url or "postgres" in _db_url.lower() or "ardor_pressure_test" in _db_url:
    raise RuntimeError("Use an isolated SQLite DATABASE_URL for this test module.")
if not _storage_dir or os.path.normpath(_storage_dir) == "/data/storage":
    raise RuntimeError("Use isolated test storage for this test module.")

import pytest
from fastapi.testclient import TestClient

from services.api.auth import hash_password
from services.api.config import settings
from services.api.database import Base, SessionLocal, engine
from services.api.main import app
from services.api.models import Artifact, AuditEvent, PressureTest, PublicShare, TestRevision, User
from services.api.shares import TOKEN_LENGTH, share_id_from_token, share_token


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _user(username, role, password="pass123"):
    with SessionLocal() as db:
        user = User(username=username, full_name=username.title(), hashed_password=hash_password(password), role=role, is_active=True)
        db.add(user)
        db.commit()
        return user.id


def _client(username, password="pass123"):
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": settings.public_origin, "X-Ardor-Session-Mode": "browser"},
    )
    assert response.status_code == 200
    return client


def _unsafe(client):
    return {"Origin": settings.public_origin, "X-CSRF-Token": client.cookies.get(settings.csrf_cookie_name)}


def _log(log_no="067FED", *, legacy=False, archived=False):
    """A log with an old and a current revision, each with one file in storage."""
    base = Path(settings.storage_dir)
    with SessionLocal() as db:
        test = PressureTest(log_no=log_no, is_archived=archived, pipecloud_added=True)
        db.add(test)
        db.flush()
        ids = {"test": test.id}
        now = datetime.now(timezone.utc)
        for label, primary, created in (("old", False, now - timedelta(days=1)), ("current", True, now)):
            rev = TestRevision(
                pressure_test_id=test.id, revision_id=f"rev-{label}", status="complete", is_primary=primary,
                operator="Andrei", created_at=created,
                metadata_json={"test_pressure": "8 bar", "pipe_numbers": ["123/1"], "internal_secret": "x"},
                metrics_json={"max_pressure_bar": 9.0},
            )
            db.add(rev)
            db.flush()
            key = f"logs/{log_no}/{label}/graph.png"
            (base / key).parent.mkdir(parents=True, exist_ok=True)
            (base / key).write_bytes(f"{label}-png".encode())
            art = Artifact(test_revision_id=rev.id, name=f"{label}.png", relative_path=f"{label}.png", file_type="graph_png",
                           size_bytes=10, sha256="0" * 64, storage_key=key)
            db.add(art)
            db.flush()
            ids[label] = art.id
        if legacy:
            db.add(PublicShare(pressure_test_id=test.id, legacy_log_no_access=True, access_count=0))
        db.commit()
        return ids


def test_token_round_trip_and_tampering():
    share_id = "2b5f0a64-8a3e-4f64-9a3b-6f8f0f1c2d3e"
    token = share_token(share_id)
    assert len(token) == TOKEN_LENGTH
    assert share_id_from_token(token) == share_id
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert share_id_from_token(tampered) is None
    assert share_id_from_token("x" * TOKEN_LENGTH) is None
    assert share_id_from_token("") is None


def test_foreman_creates_one_link_and_guest_sees_only_that_log():
    _user("fore", "foreman")
    ids = _log()
    _log("068FED")
    client = _client("fore")
    first = client.post("/api/v1/shares", json={"log_no": "067FED"}, headers=_unsafe(client))
    again = client.post("/api/v1/shares", json={"log_no": "067FED"}, headers=_unsafe(client))
    assert first.status_code == 200 and again.json()["id"] == first.json()["id"]  # no duplicates
    url = first.json()["url"]
    assert url.startswith(f"{settings.public_origin.rstrip('/')}/s/")
    token = url.rsplit("/", 1)[1]

    guest = TestClient(app)
    response = guest.get(f"/api/v1/public/shares/{token}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    body = response.json()
    assert body["log_no"] == "067FED"
    assert body["revision"]["revision_id"] == "rev-current"
    assert body["revision"]["metadata"] == {"test_pressure": "8 bar", "pipe_numbers": ["123/1"]}  # explicit fields only
    assert [a["id"] for a in body["revision"]["artifacts"]] == [ids["current"]]

    assert guest.get(f"/api/v1/public/shares/{token}/artifacts/{ids['current']}").content == b"current-png"
    # an artifact of an older revision or of another log is not reachable through this token
    assert guest.get(f"/api/v1/public/shares/{token}/artifacts/{ids['old']}").status_code == 404
    zip_response = guest.get(f"/api/v1/public/shares/{token}/zip")
    assert zip_response.status_code == 200 and zip_response.headers["content-type"] == "application/zip"

    with SessionLocal() as db:
        share = db.get(PublicShare, first.json()["id"])
        assert share.access_count == 1 and share.last_accessed_at is not None
        assert db.query(AuditEvent).filter(AuditEvent.action == "share_created").count() == 1


def test_viewer_and_guest_cannot_manage_links():
    _user("view", "viewer")
    _log()
    viewer = _client("view")
    assert viewer.post("/api/v1/shares", json={"log_no": "067FED"}, headers=_unsafe(viewer)).status_code == 403
    assert viewer.get("/api/v1/shares", params={"log_no": "067FED"}).status_code == 403
    assert TestClient(app).post("/api/v1/shares", json={"log_no": "067FED"}).status_code == 401


def test_revoked_link_stops_working():
    _user("fore", "foreman")
    _log()
    client = _client("fore")
    share = client.post("/api/v1/shares", json={"log_no": "067FED"}, headers=_unsafe(client)).json()
    token = share["url"].rsplit("/", 1)[1]
    assert client.delete(f"/api/v1/shares/{share['id']}", headers=_unsafe(client)).status_code == 200
    assert TestClient(app).get(f"/api/v1/public/shares/{token}").status_code == 404
    # a new link is a different token
    fresh = client.post("/api/v1/shares", json={"log_no": "067FED"}, headers=_unsafe(client)).json()
    assert fresh["url"] != share["url"]


def test_archived_log_is_not_public():
    _user("fore", "foreman")
    _log(archived=True, legacy=True)
    client = _client("fore")
    assert client.post("/api/v1/shares", json={"log_no": "067FED"}, headers=_unsafe(client)).status_code == 409
    assert TestClient(app).get("/api/v1/public/legacy/067FED").status_code == 404


def test_legacy_number_link_works_only_for_logs_that_kept_it():
    _log("067FED", legacy=True)
    _log("099FED", legacy=False)  # created after token links: no legacy record
    guest = TestClient(app)
    resolved = guest.get("/api/v1/public/legacy/067FED")
    assert resolved.status_code == 200
    assert guest.get(f"/api/v1/public/shares/{resolved.json()['token']}").json()["log_no"] == "067FED"
    assert guest.get("/api/v1/public/legacy/099FED").status_code == 404
    assert guest.get("/api/v1/public/legacy/000NOPE").status_code == 404


def test_legacy_link_can_be_revoked_and_globally_switched_off(monkeypatch):
    _user("fore", "foreman")
    _log("067FED", legacy=True)
    client = _client("fore")
    shares = client.get("/api/v1/shares", params={"log_no": "067FED"}).json()
    assert [s["legacy"] for s in shares] == [True]
    assert shares[0]["url"].endswith("/share/067FED")

    monkeypatch.setattr(settings, "legacy_share_links", False)
    assert TestClient(app).get("/api/v1/public/legacy/067FED").status_code == 404
    assert client.get("/api/v1/shares", params={"log_no": "067FED"}).json() == []
    monkeypatch.setattr(settings, "legacy_share_links", True)

    client.delete(f"/api/v1/shares/{shares[0]['id']}", headers=_unsafe(client))
    assert TestClient(app).get("/api/v1/public/legacy/067FED").status_code == 404


def test_link_survives_log_rename():
    _user("fore", "foreman")
    ids = _log()
    client = _client("fore")
    token = client.post("/api/v1/shares", json={"log_no": "067FED"}, headers=_unsafe(client)).json()["url"].rsplit("/", 1)[1]
    with SessionLocal() as db:
        db.get(PressureTest, ids["test"]).log_no = "067FED-R"
        db.commit()
    assert TestClient(app).get(f"/api/v1/public/shares/{token}").json()["log_no"] == "067FED-R"
