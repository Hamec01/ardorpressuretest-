"""Stage 3: the site is closed - business API needs a session; viewers only read."""

import os

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
from services.api.models import PressureTest, PublicShare, TestRevision, User


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add(User(username="view", full_name="Viewer", hashed_password=hash_password("pass123"), role="viewer", is_active=True))
        test = PressureTest(log_no="067FED")
        db.add(test)
        db.flush()
        db.add(TestRevision(pressure_test_id=test.id, revision_id="r1", metadata_json={}, metrics_json={}))
        db.add(PublicShare(pressure_test_id=test.id, legacy_log_no_access=True, access_count=0))
        db.commit()
    yield
    Base.metadata.drop_all(bind=engine)


def _viewer():
    client = TestClient(app)
    assert client.post(
        "/api/v1/auth/login",
        json={"username": "view", "password": "pass123"},
        headers={"Origin": settings.public_origin, "X-Ardor-Session-Mode": "browser"},
    ).status_code == 200
    return client


@pytest.mark.parametrize("path", [
    "/api/v1/tests",
    "/api/v1/tests/067FED",
    "/api/v1/tests/trash",
    "/api/v1/tests/artifacts/x/file",
    "/api/v1/tests/067FED/revisions/r1/zip",
    "/api/v1/records",
    "/api/v1/records/x/pdf",
    "/api/v1/records/verify/ARDOR-VRF-X",
    "/api/v1/planned-tests/lists",
])
def test_guest_cannot_read_business_data(path):
    assert TestClient(app).get(path).status_code == 401


@pytest.mark.parametrize("method,path", [
    ("post", "/api/v1/process"),
    ("post", "/api/v1/process/package"),
    ("put", "/api/v1/tests/067FED/revisions/r1/metadata"),
    ("post", "/api/v1/sync/sessions"),
])
def test_guest_cannot_change_data_or_sync(method, path):
    assert getattr(TestClient(app), method)(path, json={}).status_code == 401


def test_viewer_reads_but_cannot_change():
    client = _viewer()
    unsafe = {"Origin": settings.public_origin, "X-CSRF-Token": client.cookies.get(settings.csrf_cookie_name)}
    assert client.get("/api/v1/tests").status_code == 200
    assert client.get("/api/v1/tests/067FED").status_code == 200
    assert client.put("/api/v1/tests/067FED/revisions/r1/metadata", json={"note": "x"}, headers=unsafe).status_code == 403
    assert client.patch("/api/v1/tests/067FED/pipecloud", json={"added": True}, headers=unsafe).status_code == 403
    assert client.post("/api/v1/tests/067FED/photos", files={"photos": ("a.jpg", b"x", "image/jpeg")}, headers=unsafe).status_code == 403
    assert client.post("/api/v1/process", headers=unsafe).status_code == 403


def test_public_share_links_still_work_without_a_session():
    guest = TestClient(app)
    token = guest.get("/api/v1/public/legacy/067FED").json()["token"]
    assert guest.get(f"/api/v1/public/shares/{token}").status_code == 200
