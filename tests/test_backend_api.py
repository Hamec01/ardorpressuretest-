import io
import pytest
from fastapi.testclient import TestClient
from services.api.main import app
from services.api.database import Base, engine


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
