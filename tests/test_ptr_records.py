import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from services.api.config import settings
from services.api.database import Base, SessionLocal, engine
from services.api.main import app
from services.api.auth import seed_default_users
from wika_report.ptr_generator import generate_ptr_pdf


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_users(db)
    if settings.storage_dir.exists():
        shutil.rmtree(settings.storage_dir, ignore_errors=True)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    yield
    Base.metadata.drop_all(bind=engine)
    if settings.storage_dir.exists():
        shutil.rmtree(settings.storage_dir, ignore_errors=True)


def test_ptr_pdf_generator_standalone():
    rec_data = {
        "record_number": "PTR-2026-TEST",
        "project": "Meyer Turku NB-1400",
        "system": "Fuel Gas System",
        "ins_no": "INS-001",
        "test_date": "2026-08-19",
        "test_medium": "Water",
        "design_pressure": "10.0 bar",
        "test_pressure": "15.0 bar",
        "duration_min": "60 min",
        "status": "complete",
        "foreman_name": "Matti Meikäläinen",
        "qc_inspector": "Jari Korhonen",
        "client_surveyor": "DNV Surveyor",
        "notes": "Test completed successfully."
    }
    items_data = [
        {"item_no": 1, "pipe_number": "PIPE-101", "drawing_no": "DWG-01", "log_no": "014FED", "hold_start_bar": "15.2", "hold_end_bar": "15.1", "result": "PASS", "notes": "OK"},
        {"item_no": 2, "pipe_number": "PIPE-102", "drawing_no": "DWG-01", "log_no": "014FED", "hold_start_bar": "15.2", "hold_end_bar": "15.1", "result": "PASS", "notes": "OK"},
    ]

    pdf_bytes = generate_ptr_pdf(rec_data, items_data)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_ptr_api_flow():
    client = TestClient(app)

    # 1. Login as foreman
    foreman_res = client.post("/api/v1/auth/login", json={
        "username": "foreman_matti",
        "password": "foreman123"
    })
    assert foreman_res.status_code == 200
    token = foreman_res.json()["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # 2. Create Pressure Test Record
    create_payload = {
        "record_number": "PTR-2026-901",
        "project": "ARDOR Baltic Project",
        "system": "Main Hydraulic Line",
        "ins_no": "INS-901",
        "test_medium": "Water",
        "test_pressure": "15 bar",
        "items": [
            {
                "item_no": 1,
                "pipe_number": "P-901",
                "drawing_no": "DWG-901",
                "spool_no": "SP-01",
                "log_no": "014FED",
                "hold_start_bar": "15.2",
                "hold_end_bar": "15.1",
                "result": "PASS"
            }
        ]
    }
    create_res = client.post("/api/v1/records", json=create_payload, headers=auth_header)
    assert create_res.status_code == 200
    record_data = create_res.json()
    record_id = record_data["id"]
    assert record_data["record_number"] == "PTR-2026-901"
    assert record_data["status"] == "draft"
    assert len(record_data["items"]) == 1

    # 3. Update Record status to confirmed
    update_res = client.put(f"/api/v1/records/{record_id}", json={"status": "confirmed"}, headers=auth_header)
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "confirmed"

    # 4. Download Official PDF Blank
    pdf_res = client.get(f"/api/v1/records/{record_id}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert len(pdf_res.content) > 1000
    assert pdf_res.content.startswith(b"%PDF-")

    # 5. Query records list
    list_res = client.get("/api/v1/records?q=901")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
