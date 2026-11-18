import io
import hashlib
import uuid
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from services.api.main import app
from services.api.database import Base, engine, SessionLocal
from services.api.models import Artifact, PressureTest, PublicShare, TestRevision as PressureTestRevision
from services.api.shares import share_token


import shutil
from pathlib import Path
from services.api.config import settings
from services.api.storage import storage

# Business-behaviour tests: run as a signed-in admin (access control is tested separately).
pytestmark = pytest.mark.usefixtures("signed_in_admin")


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    if settings.storage_dir.exists():
        shutil.rmtree(settings.storage_dir, ignore_errors=True)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    yield
    Base.metadata.drop_all(bind=engine)
    if settings.storage_dir.exists():
        shutil.rmtree(settings.storage_dir, ignore_errors=True)


def test_health_endpoints():
    client = TestClient(app)
    
    r1 = client.get("/health")
    assert r1.status_code == 200
    data1 = r1.json()
    assert data1["status"] == "ok"
    assert data1["database"] == "connected"

    r2 = client.get("/api/v1/health")
    assert r2.status_code == 200
    assert r2.json()["status"] == "ok"


def test_sync_flow_and_query():
    client = TestClient(app)

    manifest_payload = {
        "manifest_version": "1.0",
        "core_version": "1.0.0",
        "log_no": "014FED",
        "revision_id": "rev_20260819_120000",
        "created_at_utc": "2026-08-19T12:00:00Z",
        "created_by": "Matti",
        "metadata": {
            "test_pressure": "15 bar",
            "system": "Main Line",
            "pipe_numbers": ["P-101", "P-102"],
            "bundle_numbers": ["B-01"]
        },
        "metrics": {
            "min_pressure_bar": 15.01,
            "max_pressure_bar": 15.20,
            "duration_formatted": "01:00:00"
        },
        "artifacts": [
            {
                "name": "014FED.png",
                "relative_path": "014FED.png",
                "file_type": "graph_png",
                "size_bytes": 100,
                "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
            }
        ]
    }

    # Step 1: Init sync session
    session_res = client.post(
        "/api/v1/sync/sessions",
        json={"idempotency_key": "idemp-001", "manifest": manifest_payload}
    )
    assert session_res.status_code == 200
    session_data = session_res.json()
    assert session_data["status"] == "new_log"
    assert len(session_data["missing_artifacts"]) == 1

    # Step 2: Upload artifact
    fake_png = io.BytesIO(b"PNG fake data bytes")
    upload_res = client.post(
        "/api/v1/sync/sessions/rev_20260819_120000/upload",
        data={
            "log_no": "014FED",
            "relative_path": "014FED.png",
            "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        },
        files={"file": ("014FED.png", fake_png, "image/png")}
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["status"] == "uploaded"

    # Step 3: Complete sync session
    complete_res = client.post(
        "/api/v1/sync/sessions/rev_20260819_120000/complete",
        json={"idempotency_key": "idemp-001", "manifest": manifest_payload}
    )
    assert complete_res.status_code == 200
    complete_data = complete_res.json()
    assert complete_data["status"] == "synced"
    assert complete_data["log_no"] == "014FED"
    assert complete_data["artifacts_count"] == 1

    # Step 4: Query test via GET /api/v1/tests/014FED
    get_res = client.get("/api/v1/tests/014FED")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["log_no"] == "014FED"
    assert len(get_data["revisions"]) == 1
    assert get_data["revisions"][0]["operator"] == "Matti"
    assert len(get_data["revisions"][0]["artifacts"]) == 1

    # Step 5: List tests via GET /api/v1/tests
    list_res = client.get("/api/v1/tests")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1


def test_photo_thumbnails_preserve_original_and_public_share_scope():
    client = TestClient(app)
    image = Image.effect_noise((1600, 1200), 100).convert("RGB")
    source = io.BytesIO()
    image.save(source, format="JPEG", quality=95)
    original_bytes = source.getvalue()

    test_id = str(uuid.uuid4())
    revision_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    broken_artifact_id = str(uuid.uuid4())
    share_id = str(uuid.uuid4())
    storage_key = f"logs/{test_id}/revisions/{revision_id}/photo.jpg"
    broken_storage_key = f"logs/{test_id}/revisions/{revision_id}/broken.jpg"

    with SessionLocal() as db:
        pressure_test = PressureTest(id=test_id, log_no="THUMBNAIL-TEST")
        revision = PressureTestRevision(
            id=revision_id,
            pressure_test_id=test_id,
            revision_id="thumbnail-test-revision",
            operator="Test",
            metadata_json={},
            metrics_json={},
        )
        artifact = Artifact(
            id=artifact_id,
            test_revision_id=revision_id,
            name="photo.jpg",
            relative_path="photo.jpg",
            file_type="photo",
            category="pipe",
            size_bytes=len(original_bytes),
            sha256=hashlib.sha256(original_bytes).hexdigest(),
            storage_key=storage_key,
        )
        broken_artifact = Artifact(
            id=broken_artifact_id,
            test_revision_id=revision_id,
            name="broken.jpg",
            relative_path="broken.jpg",
            file_type="photo",
            category="other",
            size_bytes=len(b"not an image"),
            sha256=hashlib.sha256(b"not an image").hexdigest(),
            storage_key=broken_storage_key,
        )
        share = PublicShare(id=share_id, pressure_test_id=test_id)
        db.add_all([pressure_test, revision, artifact, broken_artifact, share])
        db.commit()

    storage.store_file(storage_key, io.BytesIO(original_bytes))
    storage.store_file(broken_storage_key, io.BytesIO(b"not an image"))
    stored_path = storage.get_file_path(storage_key)
    assert stored_path is not None
    original_hash = hashlib.sha256(stored_path.read_bytes()).hexdigest()

    thumbnail_response = client.get(f"/api/v1/tests/artifacts/{artifact_id}/thumbnail")
    assert thumbnail_response.status_code == 200
    assert thumbnail_response.headers["content-type"] == "image/webp"
    assert thumbnail_response.headers["cache-control"] == "private, max-age=3600"
    with Image.open(io.BytesIO(thumbnail_response.content)) as thumbnail:
        assert thumbnail.format == "WEBP"
        assert max(thumbnail.size) <= 300
    assert len(thumbnail_response.content) <= len(original_bytes) // 4

    broken_thumbnail = client.get(f"/api/v1/tests/artifacts/{broken_artifact_id}/thumbnail")
    assert broken_thumbnail.status_code == 415

    original_response = client.get(f"/api/v1/tests/artifacts/{artifact_id}/file")
    assert original_response.status_code == 200
    assert original_response.content == original_bytes
    assert hashlib.sha256(stored_path.read_bytes()).hexdigest() == original_hash

    token = share_token(share_id)
    public_thumbnail = client.get(
        f"/api/v1/public/shares/{token}/artifacts/{artifact_id}/thumbnail"
    )
    assert public_thumbnail.status_code == 200
    assert public_thumbnail.headers["cache-control"] == "no-store"
    assert public_thumbnail.content == thumbnail_response.content

    foreign_artifact = client.get(
        f"/api/v1/public/shares/{token}/artifacts/{uuid.uuid4()}/thumbnail"
    )
    assert foreign_artifact.status_code == 404


def test_web_process_endpoint():
    client = TestClient(app)
    csv_sample_path = Path("samples/sample_1_semicolon_comma.csv")
    assert csv_sample_path.exists()

    with open(csv_sample_path, "rb") as f:
        form_data = {
            "log_no": "014FED",
            "test_pressure": "15 bar",
            "system": "Hydraulic Section A",
            "operator": "Pekka",
            "pipe_numbers_raw": "PIPE-901\nPIPE-902",
            "bundle_numbers_raw": "B-10",
            "create_pdf": "false"
        }
        files = {
            "csv_file": ("sample_1.csv", f, "text/csv")
        }
        res = client.post("/api/v1/process", data=form_data, files=files)

    assert res.status_code == 200
    data = res.json()
    assert data["log_no"] == "014FED"
    assert len(data["revisions"]) == 1
    rev = data["revisions"][0]
    assert rev["operator"] == "Pekka"
    assert len(rev["artifacts"]) >= 3  # CSV, PNG, XLSX, TXT
