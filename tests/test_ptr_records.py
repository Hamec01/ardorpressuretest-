import base64
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
        "notes": "Test completed successfully.",
        "verification_code": "ARDOR-VRF-9821-2026",
        "confirmed_by_name": "Matti Meikäläinen",
        "confirmed_by_role": "foreman"
    }
    items_data = [
        {"item_no": 1, "pipe_number": "PIPE-101", "drawing_no": "DWG-01", "log_no": "014FED", "hold_start_bar": "15.2", "hold_end_bar": "15.1", "result": "PASS", "notes": "OK"},
        {"item_no": 2, "pipe_number": "PIPE-102", "drawing_no": "DWG-01", "log_no": "014FED", "hold_start_bar": "15.2", "hold_end_bar": "15.1", "result": "PASS", "notes": "OK"},
    ]

    pdf_bytes = generate_ptr_pdf(rec_data, items_data)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_ptr_api_flow_with_signatures_and_verification():
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

    # 3. Attach Digital Signature Image
    # 1x1 transparent png in base64
    fake_png_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    sig_res = client.post(f"/api/v1/records/{record_id}/signature", json={"image_base64": fake_png_b64}, headers=auth_header)
    assert sig_res.status_code == 200
    assert sig_res.json()["signature_image_path"] is not None

    # 4. Confirm Record with Digital Verification Seal
    confirm_res = client.post(f"/api/v1/records/{record_id}/confirm", headers=auth_header)
    assert confirm_res.status_code == 200
    confirmed_data = confirm_res.json()
    assert confirmed_data["status"] == "confirmed"
    assert confirmed_data["verification_code"].startswith("ARDOR-VRF-")
    assert "Matti Meik" in confirmed_data["confirmed_by_name"]
    assert confirmed_data["sha256_hash"] is not None
    vrf_code = confirmed_data["verification_code"]

    # 5. Public Verification Endpoint Check
    verify_res = client.get(f"/api/v1/records/verify/{vrf_code}")
    assert verify_res.status_code == 200
    vrf_json = verify_res.json()
    assert vrf_json["valid"] is True
    assert vrf_json["verification_code"] == vrf_code
    assert "Matti Meik" in vrf_json["confirmed_by_name"]

    # 6. Download Verified Official PDF Blank
    pdf_res = client.get(f"/api/v1/records/{record_id}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert len(pdf_res.content) > 1000
    assert pdf_res.content.startswith(b"%PDF-")

    # 7. Upload External Signed Copy PDF
    fake_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    upload_res = client.post(
        f"/api/v1/records/{record_id}/signed-copy",
        files={"file": ("signed_copy.pdf", fake_pdf, "application/pdf")},
        headers=auth_header
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["status"] == "signed"
    assert upload_res.json()["signed_copy_path"] is not None
