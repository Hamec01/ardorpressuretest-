import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from services.api.models import Base, PressureTest, TestRevision, Artifact, AuditEvent, User
from services.api.routes.tests import update_pipecloud_status, list_or_search_pressure_tests
from services.api.schemas import PipeCloudUpdateRequest
from wika_report.sync_queue import SyncQueue
from wika_report.sync_client import SyncClient


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed test user
    user = User(
        id="user-123",
        username="matti_foreman",
        full_name="Matti Meikäläinen",
        role="foreman",
        hashed_password="hash",
        is_active=True
    )
    session.add(user)

    # Seed pressure test
    test = PressureTest(
        id="test-log-044",
        log_no="044-1",
        pipecloud_added=False,
        is_archived=False
    )
    session.add(test)
    session.commit()

    yield session
    session.close()


def test_pipecloud_toggle_and_audit(db_session):
    user = db_session.query(User).filter(User.username == "matti_foreman").first()

    # 1. Update PipeCloud status to True
    req = PipeCloudUpdateRequest(added=True, idempotency_key="idemp_key_001")
    resp = update_pipecloud_status(log_no="044-1", payload=req, current_user=user, db=db_session)

    assert resp.log_no == "044-1"
    assert resp.pipecloud_added is True
    assert resp.pipecloud_updated_by_name == "Matti Meikäläinen"

    # Check db
    test = db_session.query(PressureTest).filter(PressureTest.log_no == "044-1").first()
    assert test.pipecloud_added is True

    # Check audit log
    event = db_session.query(AuditEvent).filter(AuditEvent.action == "pipecloud_status_changed").first()
    assert event is not None
    assert event.entity_type == "pressure_test"
    assert event.details_json["old_value"] is False
    assert event.details_json["new_value"] is True
    assert event.details_json["idempotency_key"] == "idemp_key_001"

    # 2. Update PipeCloud status back to False
    req2 = PipeCloudUpdateRequest(added=False, idempotency_key="idemp_key_002")
    resp2 = update_pipecloud_status(log_no="044-1", payload=req2, current_user=user, db=db_session)

    assert resp2.pipecloud_added is False
    test2 = db_session.query(PressureTest).filter(PressureTest.log_no == "044-1").first()
    assert test2.pipecloud_added is False


def test_pipecloud_filter(db_session):
    # Add a second test that is added to PipeCloud
    test2 = PressureTest(
        id="test-log-045",
        log_no="045-1",
        pipecloud_added=True,
        is_archived=False
    )
    db_session.add(test2)
    db_session.commit()

    # Filter all
    all_tests = list_or_search_pressure_tests(q=None, pipecloud_filter="all", db=db_session)
    assert len(all_tests) == 2

    # Filter added
    added_tests = list_or_search_pressure_tests(q=None, pipecloud_filter="added", db=db_session)
    assert len(added_tests) == 1
    assert added_tests[0].log_no == "045-1"

    # Filter not added
    not_added_tests = list_or_search_pressure_tests(q=None, pipecloud_filter="not_added", db=db_session)
    assert len(not_added_tests) == 1
    assert not_added_tests[0].log_no == "044-1"


def test_offline_sync_queue_pipecloud(tmp_path):
    queue_db = tmp_path / "test_queue.db"
    queue = SyncQueue(queue_db)

    # Enqueue PipeCloud update
    op_id = queue.enqueue_pipecloud_update(log_no="044-1", added=True, updated_by="Operator")
    assert op_id.startswith("op_pc_044-1_")

    pending = queue.get_pending_items()
    assert len(pending) == 1
    assert pending[0].operation_type == "pipecloud_status_update"
    assert pending[0].log_no == "044-1"
    
    payload = json.loads(pending[0].payload_json)
    assert payload["added"] is True

    # Update status to synced
    queue.update_status(op_id, status="synced", receipt_id="receipt_pc_044-1_True")
    pending_after = queue.get_pending_items()
    assert len(pending_after) == 0
