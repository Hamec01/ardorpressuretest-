import json
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from services.api.main import app
from services.api.database import Base, engine
from wika_report.sync_queue import SyncQueue
from wika_report.sync_client import SyncClient


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_sqlite_sync_queue_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_queue.db"
        queue = SyncQueue(db_path=db_path)

        manifest_file = Path(tmpdir) / "manifest.json"
        manifest_file.write_text("{}", encoding="utf-8")

        # 1. Enqueue
        op_id = queue.enqueue_revision(
            log_no="014FED",
            revision_id="rev_001",
            manifest_path=manifest_file
        )
        assert op_id.startswith("op_014FED_rev_001_")

        # 2. Get pending
        pending = queue.get_pending_items()
        assert len(pending) == 1
        assert pending[0].log_no == "014FED"
        assert pending[0].status == "pending"

        # 3. Update status
        queue.update_status(op_id, status="synced", receipt_id="rcpt_123")
        summary = queue.get_summary()
        assert summary["synced"] == 1
        assert summary["pending"] == 0

        # 4. Duplicate enqueue returns same op_id
        op_id2 = queue.enqueue_revision(
            log_no="014FED",
            revision_id="rev_001",
            manifest_path=manifest_file
        )
        assert op_id2 == op_id


def test_sync_client_integration_with_fastapi():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_queue.db"
        queue = SyncQueue(db_path=db_path)

        log_dir = Path(tmpdir) / "014FED"
        log_dir.mkdir()

        # Create dummy graph file
        graph_file = log_dir / "014FED.png"
        graph_file.write_bytes(b"dummy png content")

        # Create manifest
        manifest_data = {
            "manifest_version": "1.0",
            "core_version": "1.0.0",
            "log_no": "014FED",
            "revision_id": "rev_20260819_130000",
            "created_at_utc": "2026-08-19T13:00:00Z",
            "created_by": "Operator Matti",
            "metadata": {
                "system": "Hydraulic Line A",
                "pipe_numbers": ["P-10", "P-11"]
            },
            "metrics": {
                "min_pressure_bar": 10.5,
                "max_pressure_bar": 10.8
            },
            "artifacts": [
                {
                    "name": "014FED.png",
                    "relative_path": "014FED.png",
                    "file_type": "graph_png",
                    "size_bytes": len(b"dummy png content"),
                    "sha256": "fake_sha_test_123456"
                }
            ]
        }
        manifest_file = log_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

        # Enqueue item
        op_id = queue.enqueue_revision("014FED", "rev_20260819_130000", manifest_file)
        item = queue.get_pending_items()[0]

        # Use test client adapter to test sync
        test_client = TestClient(app)
        
        # Step 1: Session init
        s_res = test_client.post("/api/v1/sync/sessions", json={
            "idempotency_key": item.operation_id,
            "manifest": manifest_data
        })
        assert s_res.status_code == 200

        # Step 2: Upload
        with open(graph_file, "rb") as f:
            up_res = test_client.post(
                f"/api/v1/sync/sessions/{item.revision_id}/upload",
                data={"log_no": item.log_no, "relative_path": "014FED.png", "sha256": "fake_sha_test_123456"},
                files={"file": ("014FED.png", f, "image/png")}
            )
        assert up_res.status_code == 200

        # Step 3: Complete
        c_res = test_client.post(f"/api/v1/sync/sessions/{item.revision_id}/complete", json={
            "idempotency_key": item.operation_id,
            "manifest": manifest_data
        })
        assert c_res.status_code == 200
        receipt_id = c_res.json()["receipt_id"]
        queue.update_status(item.operation_id, status="synced", receipt_id=receipt_id)

        # Verify queue state
        synced_item = queue.get_all_items()[0]
        assert synced_item.status == "synced"
        assert synced_item.receipt_id == receipt_id
