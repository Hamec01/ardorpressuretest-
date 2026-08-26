"""
Attach-CSV-to-existing-draft feature (branch feature/attach-csv-to-draft).

Covers: a Log can be started as a draft (metadata + photos, no CSV yet — task spec
AGENTS.md §10.5 / PRODUCT_REQUIREMENTS.md §6.2 "Неполное испытание можно сохранить как Draft"),
and later completed by resubmitting the same Log No. with a CSV file attached. Per
AGENTS.md §6 (revision immutability, no overwrite): completing a draft must create a brand
new "complete" revision rather than mutating the draft revision in place, and the draft's
already-entered photos/pipe numbers must carry forward automatically so the operator never
has to re-supply them. Uses only the synthetic sample CSVs under samples/ (AGENTS.md §6.8 —
tests must use synthetic/anonymized materials, never real customer data).
"""
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.database import Base, engine, SessionLocal
from services.api.main import app
from services.api.models import AuditEvent

import shutil
from services.api.config import settings


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


SAMPLE_CSV = Path("samples/sample_1_semicolon_comma.csv")
TINY_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a4944415478da6360000002000155a2261200000000"
    "49454e44ae426082"
)


def _make_draft(client: TestClient, log_no: str, pipe_numbers_raw: str = "122153/41\n122153/21", with_photo: bool = True):
    form_data = {
        "log_no": log_no,
        "test_pressure": "15 bar",
        "system": "Fuel Gas System",
        "operator": "Matti",
        "project": "ARDOR Pipeline",
        "ins_no": "INS-2026-001",
        "wika_nr": "BG516-GDTZ-13-D",
        "note": "Draft created before CSV was ready",
        "pipe_numbers_raw": pipe_numbers_raw,
        "bundle_numbers_raw": "",
        "create_pdf": "false",
    }
    files = []
    if with_photo:
        files.append(("pipe_photos", ("pipe_evidence.png", io.BytesIO(TINY_PNG_BYTES), "image/png")))
    res = client.post("/api/v1/process", data=form_data, files=files or None)
    assert res.status_code == 200, res.text
    return res.json()


def _attach_csv(client: TestClient, log_no: str, extra_form: dict | None = None):
    with open(SAMPLE_CSV, "rb") as f:
        form_data = {
            "log_no": log_no,
            "test_pressure": "15 bar",
            "system": "Fuel Gas System",
            "operator": "Matti",
            "create_pdf": "false",
        }
        if extra_form:
            form_data.update(extra_form)
        files = {"csv_file": ("sample_1.csv", f, "text/csv")}
        res = client.post("/api/v1/process", data=form_data, files=files)
    return res


def test_draft_creation_without_csv_has_no_metrics_and_no_source_csv_artifact():
    client = TestClient(app)
    assert SAMPLE_CSV.exists()

    created = _make_draft(client, "DRAFT001")
    assert created["log_no"] == "DRAFT001"
    assert len(created["revisions"]) == 1
    rev = created["revisions"][0]
    assert rev["status"] == "draft"
    assert rev["metrics_json"] == {}
    assert not any(a["file_type"] == "source_csv" for a in rev["artifacts"])
    assert any(a["file_type"] == "photo" for a in rev["artifacts"])


def test_attach_csv_creates_new_complete_revision_and_keeps_draft_revision():
    client = TestClient(app)
    _make_draft(client, "DRAFT002")

    res = _attach_csv(client, "DRAFT002")
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["log_no"] == "DRAFT002"
    assert len(data["revisions"]) == 2, "attaching a CSV must create a NEW revision, never overwrite the draft"

    by_status = {r["status"]: r for r in data["revisions"]}
    assert "draft" in by_status and "complete" in by_status
    assert by_status["draft"]["is_primary"] is False, "the old draft revision must be demoted, not deleted"
    assert by_status["complete"]["is_primary"] is True
    assert by_status["complete"]["metrics_json"] != {}
    assert any(a["file_type"] == "source_csv" for a in by_status["complete"]["artifacts"])


def test_attach_csv_carries_forward_draft_photo_without_reupload():
    client = TestClient(app)
    draft = _make_draft(client, "DRAFT003", with_photo=True)
    draft_photo_artifacts = [a for a in draft["revisions"][0]["artifacts"] if a["file_type"] == "photo"]
    assert len(draft_photo_artifacts) == 1
    draft_photo_sha = draft_photo_artifacts[0]["sha256"]

    # Attach CSV WITHOUT re-uploading any photo.
    res = _attach_csv(client, "DRAFT003")
    assert res.status_code == 200, res.text
    data = res.json()

    complete_rev = next(r for r in data["revisions"] if r["status"] == "complete")
    complete_photo_artifacts = [a for a in complete_rev["artifacts"] if a["file_type"] == "photo"]
    assert len(complete_photo_artifacts) == 1, "the draft's photo must be carried forward into the new complete revision"
    assert complete_photo_artifacts[0]["sha256"] == draft_photo_sha, "carried-forward photo content must be byte-identical (same SHA-256)"

    # The old draft revision's own photo artifact must still exist too (nothing deleted/moved).
    draft_rev_after = next(r for r in data["revisions"] if r["status"] == "draft")
    assert any(a["file_type"] == "photo" and a["sha256"] == draft_photo_sha for a in draft_rev_after["artifacts"])


def test_attach_csv_carries_forward_pipe_numbers_when_not_resupplied():
    client = TestClient(app)
    _make_draft(client, "DRAFT004", pipe_numbers_raw="122153/41\n122153/77", with_photo=False)

    # Attach CSV with an empty pipe_numbers_raw — should NOT wipe out the draft's pipe numbers.
    res = _attach_csv(client, "DRAFT004", extra_form={"pipe_numbers_raw": "", "bundle_numbers_raw": ""})
    assert res.status_code == 200, res.text
    data = res.json()

    complete_rev = next(r for r in data["revisions"] if r["status"] == "complete")
    pipe_numbers = complete_rev["metadata_json"].get("pipe_numbers", [])
    assert set(pipe_numbers) == {"122153/41", "122153/77"}


def test_attach_csv_explicit_pipe_numbers_override_draft():
    client = TestClient(app)
    _make_draft(client, "DRAFT005", pipe_numbers_raw="OLD/1\nOLD/2", with_photo=False)

    res = _attach_csv(client, "DRAFT005", extra_form={"pipe_numbers_raw": "NEW/9", "bundle_numbers_raw": ""})
    assert res.status_code == 200, res.text
    data = res.json()

    complete_rev = next(r for r in data["revisions"] if r["status"] == "complete")
    pipe_numbers = complete_rev["metadata_json"].get("pipe_numbers", [])
    assert pipe_numbers == ["NEW/9"], "explicitly supplied pipe numbers must win over the draft's own"


def test_attach_csv_records_audit_event():
    client = TestClient(app)
    _make_draft(client, "DRAFT006", with_photo=False)
    res = _attach_csv(client, "DRAFT006")
    assert res.status_code == 200, res.text

    db = SessionLocal()
    try:
        events = db.query(AuditEvent).filter(AuditEvent.action == "csv_attached_to_draft").all()
        assert len(events) == 1
        details = events[0].details_json
        assert details["log_no"] == "DRAFT006"
    finally:
        db.close()


def test_new_test_from_scratch_with_csv_unaffected_no_audit_event():
    """A brand-new Log No. going straight to a complete revision (no prior draft) must behave
    exactly as before this feature — no carry-forward, no csv_attached_to_draft audit event."""
    client = TestClient(app)
    res = _attach_csv(client, "FRESH001")
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data["revisions"]) == 1
    assert data["revisions"][0]["status"] == "complete"

    db = SessionLocal()
    try:
        events = db.query(AuditEvent).filter(AuditEvent.action == "csv_attached_to_draft").all()
        assert len(events) == 0
    finally:
        db.close()
