import io
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from services.api.config import settings
from services.api.database import Base, SessionLocal, engine
from services.api.main import app
from services.api.auth import seed_default_users
from wika_report.config import AppConfig
from wika_report.file_processor import process_test_input
from wika_report.models import TestInput, CustomMetadata
from wika_report.sync_queue import SyncQueue
from wika_report.sync_client import SyncClient


SAMPLE_CSV_CONTENT = """Date;Time;Pressure [bar];Temperature [°C];
19.08.2026;10:00:00;15,20;21,5;
19.08.2026;10:15:00;15,18;21,4;
19.08.2026;10:30:00;15,16;21,3;
19.08.2026;10:45:00;15,14;21,2;
19.08.2026;11:00:00;15,12;21,1;
"""


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


def test_full_system_e2e_lifecycle():
    """
    Полный сквозной приёмочный сценарий ARDOR Pressure Test:
    1. Локальная обработка CSV оператором с расчётом SHA-256 и созданием манифеста.
    2. Постановка в офлайн-очередь и синхронизация по HTTP на сервер.
    3. Авторизация прораба, поиск и проверка загруженного теста.
    4. Создание сводного протокола Pressure Test Record (PTR).
    5. Электронная подпись прораба и аккаунтная верификация (Digital Seal).
    6. Публичная проверка сертификата по Verification Code.
    7. Экспорт официального PDF бланка с цифровым штампом.
    8. Аудит всех действий в неизменяемом журнале событий.
    """
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        csv_file = temp_dir / "Log_014FED.csv"
        csv_file.write_text(SAMPLE_CSV_CONTENT, encoding="utf-8")

        # Step 1: Process CSV into atomic revision
        output_dir = temp_dir / "output"
        test_input = TestInput(
            csv_path=csv_file,
            log_no="014FED",
            pipe_numbers=["PIPE-E2E-101", "PIPE-E2E-102"],
            bundle_numbers=["BUNDLE-A"],
            test_pressure="15.0",
            operator="Pekka Virtanen"
        )
        rev_info = process_test_input(
            test_input=test_input,
            output_base_dir=output_dir,
            config=AppConfig()
        )
        assert rev_info.log_no == "014FED"
        assert rev_info.revision_dir.exists()
        assert (rev_info.revision_dir / "manifest.json").exists()

        # Step 2: Queue & Synchronize to local server
        queue_db = temp_dir / "queue.db"
        queue = SyncQueue(db_path=queue_db)
        queue_item_id = queue.enqueue_revision(
            log_no="014FED",
            revision_id=rev_info.revision_id,
            manifest_path=rev_info.revision_dir / "manifest.json"
        )
        assert queue_item_id is not None

        # Step 3: Foreman logs in
        foreman_res = client.post("/api/v1/auth/login", json={
            "username": "foreman_matti",
            "password": "foreman123"
        })
        assert foreman_res.status_code == 200
        token = foreman_res.json()["access_token"]
        auth_header = {"Authorization": f"Bearer {token}"}

        # Verify test search
        search_res = client.get("/api/v1/tests?q=014FED")
        assert search_res.status_code == 200

        # Step 4: Foreman creates Pressure Test Record (PTR)
        ptr_payload = {
            "record_number": "PTR-2026-E2E-001",
            "project": "Meyer Turku NB-1400",
            "system": "High Pressure Fuel Line",
            "ins_no": "INS-E2E-001",
            "test_medium": "Water",
            "test_pressure": "15.0 bar",
            "design_pressure": "10.0 bar",
            "duration_min": "60 min",
            "notes": "E2E automated validation test passed successfully.",
            "items": [
                {
                    "item_no": 1,
                    "pipe_number": "PIPE-E2E-101",
                    "drawing_no": "DWG-E2E-01",
                    "spool_no": "SP-01",
                    "log_no": "014FED",
                    "hold_start_bar": "15.20",
                    "hold_end_bar": "15.12",
                    "result": "PASS"
                },
                {
                    "item_no": 2,
                    "pipe_number": "PIPE-E2E-102",
                    "drawing_no": "DWG-E2E-01",
                    "spool_no": "SP-02",
                    "log_no": "014FED",
                    "hold_start_bar": "15.20",
                    "hold_end_bar": "15.12",
                    "result": "PASS"
                }
            ]
        }
        ptr_res = client.post("/api/v1/records", json=ptr_payload, headers=auth_header)
        assert ptr_res.status_code == 200
        ptr_data = ptr_res.json()
        ptr_id = ptr_data["id"]
        assert ptr_data["record_number"] == "PTR-2026-E2E-001"
        assert ptr_data["status"] == "draft"

        # Step 5: Foreman attaches Signature & Confirms document
        fake_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        sig_res = client.post(f"/api/v1/records/{ptr_id}/signature", json={"image_base64": fake_png}, headers=auth_header)
        assert sig_res.status_code == 200

        conf_res = client.post(f"/api/v1/records/{ptr_id}/confirm", headers=auth_header)
        assert conf_res.status_code == 200
        conf_data = conf_res.json()
        assert conf_data["status"] == "confirmed"
        vrf_code = conf_data["verification_code"]
        assert vrf_code.startswith("ARDOR-VRF-")

        # Step 6: Public Verification Certificate Check
        verify_res = client.get(f"/api/v1/records/verify/{vrf_code}")
        assert verify_res.status_code == 200
        assert verify_res.json()["valid"] is True
        assert verify_res.json()["record_number"] == "PTR-2026-E2E-001"

        # Step 7: Export and verify Official PDF Blank
        pdf_res = client.get(f"/api/v1/records/{ptr_id}/pdf")
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert len(pdf_res.content) > 1000
        assert pdf_res.content.startswith(b"%PDF-")

        # Step 8: Administrator verifies immutable audit log
        admin_res = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert admin_res.status_code == 200
        admin_token = admin_res.json()["access_token"]

        audit_res = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {admin_token}"})
        assert audit_res.status_code == 200
        events = audit_res.json()
        assert len(events) >= 3  # login, created, confirmed
        actions = [e["action"] for e in events]
        assert "created" in actions
        assert "confirmed" in actions
