"""Feedback 2026-11-18 (docs/feedback/Исправления_2026-11-18.pdf).

1. Empty log fields must not be filled with old example values (System 64700, Ins.No
   NB1402PM-13388, 24bar, ...) on the graph or in the log metadata.
2. Corrections change only the protocol: the log's stored files stay as they are, the
   PTR draws its own copy of the graph with the PTR values.
3. The PTR attachment page prints an English evaluation (never transliterated Russian)
   and the foreman can correct the attachment fields from the PTR itself.
Synthetic data only (samples/).
"""
import json
import re
import shutil
import zlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.auth import seed_default_users
from services.api.config import settings
from services.api.database import Base, SessionLocal, engine
from services.api.main import app
from services.api.models import Artifact, TestRevision
from services.api.storage import storage
from wika_report.config import AppConfig
from wika_report.file_processor import process_test_input
from wika_report.models import TestInput
from wika_report.ptr_generator import (
    NOT_EVALUATED,
    format_bar,
    generate_full_composite_ptr_pdf,
    resolve_attachment_fields,
    resolve_evaluation_status,
)

pytestmark = pytest.mark.usefixtures("signed_in_admin")

SAMPLE_CSV = Path("samples/sample_1_semicolon_comma.csv")


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


def _pdf_text(pdf_bytes: bytes) -> str:
    chunks = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S):
        raw = match.group(1)
        try:
            chunks.append(zlib.decompress(raw).decode("latin-1"))
        except zlib.error:
            chunks.append(raw.decode("latin-1"))
    return "\n".join(chunks)


def _upload_log(client: TestClient, log_no: str, **fields) -> dict:
    form = {"log_no": log_no, "operator": "Tester", "create_pdf": "true", "pipe_numbers_raw": "131104/1"}
    form.update(fields)
    with open(SAMPLE_CSV, "rb") as handle:
        res = client.post("/api/v1/process", data=form, files={"csv_file": ("Log 138.csv", handle, "text/csv")})
    assert res.status_code == 200, res.text
    return res.json()


def _foreman_headers(client: TestClient) -> dict:
    res = client.post("/api/v1/auth/login", json={"username": "foreman_matti", "password": "foreman123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# --------------------------------------------------------------------------- 1. no example defaults

def test_core_keeps_empty_fields_empty(tmp_path):
    result = process_test_input(TestInput(csv_path=SAMPLE_CSV, log_no="900FED"), output_base_dir=tmp_path, config=AppConfig())
    assert result.success, result.error_message
    import json
    meta = json.loads(result.manifest_path.read_text(encoding="utf-8"))["metadata"]
    assert meta["system"] == ""
    assert meta["ins_no"] == ""
    assert meta["project"] == ""
    assert meta["test_pressure"] == ""
    assert meta["wika_nr"] == ""
    assert "64700" not in json.dumps(meta)
    assert "NB1402PM-13388" not in json.dumps(meta)


def test_web_upload_without_system_and_ins_no_stores_no_example_values():
    client = TestClient(app)
    test = _upload_log(client, "901FED", test_pressure="18 bar")
    meta = test["revisions"][0]["metadata_json"]
    assert meta["system"] == ""
    assert meta["ins_no"] == ""
    assert meta["test_pressure"] == "18 bar"


# --------------------------------------------------------------------------- 2. only the protocol changes

def test_metadata_edit_does_not_touch_log_files():
    client = TestClient(app)
    test = _upload_log(client, "902FED", test_pressure="18 bar")
    rev = test["revisions"][0]
    before = {a["id"]: a["sha256"] for a in rev["artifacts"]}

    res = client.put(
        f"/api/v1/tests/902FED/revisions/{rev['revision_id']}/metadata",
        json={"system": "Fuel Gas", "ins_no": "INS-777"},
    )
    assert res.status_code == 200, res.text
    new_rev = res.json()["revisions"][0]
    assert {a["id"]: a["sha256"] for a in new_rev["artifacts"]} == before
    with SessionLocal() as db:
        assert db.query(TestRevision).filter(TestRevision.id == new_rev["id"]).one().metadata_json["system"] == "Fuel Gas"


def test_ptr_graph_is_drawn_with_ptr_values(monkeypatch, tmp_path):
    import wika_report.file_processor as fp

    drawn = {}
    real_render = fp.render_graph_png

    def spy(csv_path, metadata, output_path, config=None):
        drawn.update(metadata)
        return real_render(csv_path, metadata, output_path, config)

    monkeypatch.setattr(fp, "render_graph_png", spy)
    csv_path = Path("samples") / sorted(p.name for p in Path("samples").glob("*.csv"))[0]
    stored_graph = tmp_path / "stored.png"
    real_render(csv_path, {"system": "64700"}, stored_graph)
    log = {
        "log_no": "138FED",
        "metadata": {"system": "64700", "ins_no": "NB1402PM-13388", "test_pressure": "18 bar"},
        "metrics": {},
        "attachment_overrides": {"system": "Fuel Gas", "ins_no": "INS-1"},
        "csv_path": str(csv_path),
        "include_measurement_table": False,
        "artifacts": [{"name": "g.png", "file_type": "graph_png", "file_path": str(stored_graph)}],
    }
    stored_bytes = stored_graph.read_bytes()
    generate_full_composite_ptr_pdf({"record_number": "PTR-G"}, [], [log])
    assert drawn["system"] == "Fuel Gas"
    assert drawn["ins_no"] == "INS-1"
    assert drawn["log_no"] == "138FED"
    assert stored_graph.read_bytes() == stored_bytes  # the log's own graph is untouched


def test_manual_evaluation_is_validated_and_stored():
    client = TestClient(app)
    test = _upload_log(client, "903FED")
    revision_id = test["revisions"][0]["revision_id"]

    bad = client.put(f"/api/v1/tests/903FED/revisions/{revision_id}/metadata", json={"manual_evaluation": "maybe"})
    assert bad.status_code == 422

    ok = client.put(f"/api/v1/tests/903FED/revisions/{revision_id}/metadata", json={"manual_evaluation": "pass"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["revisions"][0]["metadata_json"]["manual_evaluation"] == "PASS"


# --------------------------------------------------------------------------- 3. PTR attachment

def test_evaluation_never_prints_russian_and_follows_priority():
    russian = {"metrics": {"evaluation_status": "Не оценивалось"}}
    assert resolve_evaluation_status(russian) == NOT_EVALUATED
    assert resolve_evaluation_status({**russian, "item_results": ["PASS", "PASS"]}) == "PASS"
    assert resolve_evaluation_status({**russian, "item_results": ["PASS", "FAIL"]}) == "FAIL"
    assert resolve_evaluation_status({**russian, "metadata": {"manual_evaluation": "FAIL"}, "item_results": ["PASS"]}) == "FAIL"
    assert resolve_evaluation_status({
        **russian,
        "metadata": {"manual_evaluation": "FAIL"},
        "attachment_overrides": {"evaluation_status": "PASS"},
    }) == "PASS"


def test_attachment_fields_prefer_ptr_corrections():
    entry = {
        "metadata": {"ins_no": "NB1402PM-13388", "system": "", "project": "Icon"},
        "attachment_overrides": {"system": "Fuel Gas"},
    }
    fields = resolve_attachment_fields(entry, {"ins_no": "INS-PTR"})
    assert fields["system"] == "Fuel Gas"
    assert fields["project"] == "Icon"
    assert fields["ins_no"] == "INS-PTR"  # the PTR's own Inspection No wins over the log's
    entry["attachment_overrides"]["ins_no"] = "INS-LOG-1"
    assert resolve_attachment_fields(entry, {"ins_no": "INS-PTR"})["ins_no"] == "INS-LOG-1"


def test_format_bar_rounds_long_floats():
    assert format_bar(18.601218439716313) == "18.601"
    assert format_bar(None) == "-"
    assert format_bar("n/a") == "n/a"


def test_composite_pdf_attachment_page_content():
    pdf = generate_full_composite_ptr_pdf(
        record_data={"record_number": "PTR-TEST-1", "ins_no": ""},
        items_data=[{"item_no": 1, "pipe_number": "131104/1", "log_no": "138FED", "result": "PASS"}],
        logs_data=[{
            "log_no": "138FED",
            "revision_id": "r1",
            "metadata": {"ins_no": "NB1402PM-13388", "system": "", "project": "Icon"},
            "metrics": {"evaluation_status": "Не оценивалось", "mean_pressure_bar": 18.601218439716313},
            "attachment_overrides": {"ins_no": "INS-NEW-42"},
            "item_results": ["PASS"],
            "pipecloud_data": {"131104/1": {"drawing": "D.1403.006D", "spool_number": "9058", "pipeline": "61220P1012"}},
            "selected_pipe_numbers": ["131104/1"],
            "include_measurement_table": False,
            "artifacts": [],
        }],
    )
    text = _pdf_text(pdf)
    assert "INS-NEW-42" in text
    assert "NB1402PM-13388" not in text
    assert "Ne otsenivalos" not in text
    assert "18.601 bar" in text
    assert "18.601218" not in text
    assert "PipeCloud Data:" in text
    assert "61220P1012" in text


def test_ptr_log_overrides_are_saved_and_survive_log_resave():
    client = TestClient(app)
    test = _upload_log(client, "904FED", test_pressure="18 bar")
    rev = test["revisions"][0]
    headers = _foreman_headers(client)

    log_ref = {"pressure_test_id": test["id"], "test_revision_id": rev["id"], "selected_pipe_numbers": ["131104/1"]}
    created = client.post("/api/v1/records", json={
        "record_number": "PTR-TEST-904",
        "items": [{"item_no": 1, "pipe_number": "131104/1", "log_no": "904FED", "result": "PASS"}],
        "logs": [log_ref],
    }, headers=headers)
    assert created.status_code == 200, created.text
    record = created.json()
    record_log_id = record["logs"][0]["id"]
    assert record["logs"][0]["log_no"] == "904FED"

    updated = client.put(f"/api/v1/records/{record['id']}", json={
        "log_overrides": {record_log_id: {"ins_no": " INS-904 ", "evaluation_status": "pass", "system": ""}},
    }, headers=headers)
    assert updated.status_code == 200, updated.text
    overrides = updated.json()["logs"][0]["metadata_snapshot"]["attachment_overrides"]
    assert overrides == {"ins_no": "INS-904", "evaluation_status": "PASS"}

    bad = client.put(f"/api/v1/records/{record['id']}", json={
        "log_overrides": {record_log_id: {"evaluation_status": "OK"}},
    }, headers=headers)
    assert bad.status_code == 422

    resaved = client.put(f"/api/v1/records/{record['id']}", json={"logs": [log_ref]}, headers=headers)
    assert resaved.status_code == 200, resaved.text
    assert resaved.json()["logs"][0]["metadata_snapshot"]["attachment_overrides"]["ins_no"] == "INS-904"

    full_pdf = client.get(f"/api/v1/records/{record['id']}/full-pdf")
    assert full_pdf.status_code == 200
    text = _pdf_text(full_pdf.content)
    assert "INS-904" in text
    assert "PASS" in text


def test_log_in_confirmed_ptr_cannot_be_edited():
    client = TestClient(app)
    test = _upload_log(client, "905FED")
    rev = test["revisions"][0]
    headers = _foreman_headers(client)
    created = client.post("/api/v1/records", json={
        "record_number": "PTR-TEST-905",
        "logs": [{"pressure_test_id": test["id"], "test_revision_id": rev["id"]}],
    }, headers=headers)
    assert created.status_code == 200, created.text
    confirm = client.post(f"/api/v1/records/{created.json()['id']}/confirm", headers=headers)
    assert confirm.status_code == 200, confirm.text

    res = client.put(f"/api/v1/tests/905FED/revisions/{rev['revision_id']}/metadata", json={"system": "X"})
    assert res.status_code == 409
    assert "PTR-TEST-905" in res.json()["detail"]


def test_live_preview_uses_unsaved_values_and_writes_nothing():
    client = TestClient(app)
    test = _upload_log(client, "906FED", test_pressure="18 bar")
    rev = test["revisions"][0]
    headers = _foreman_headers(client)
    created = client.post("/api/v1/records", json={
        "record_number": "PTR-TEST-906",
        "project": "Saved Project",
        "items": [{"item_no": 1, "pipe_number": "131104/1", "log_no": "906FED", "result": "PASS"}],
        "logs": [{"pressure_test_id": test["id"], "test_revision_id": rev["id"], "selected_pipe_numbers": ["131104/1"]}],
    }, headers=headers)
    assert created.status_code == 200, created.text
    record = created.json()
    record_log_id = record["logs"][0]["id"]

    preview = client.post(f"/api/v1/records/{record['id']}/preview-pdf?kind=full", json={
        "project": "Draft Project",
        "items": [{"item_no": 1, "pipe_number": "131104/1", "log_no": "906FED", "result": "FAIL"}],
        "log_overrides": {record_log_id: {"ins_no": "INS-DRAFT-906"}},
    }, headers=headers)
    assert preview.status_code == 200, preview.text
    assert preview.headers["cache-control"] == "no-store"
    pages = json.loads(preview.headers["x-ptr-log-pages"])
    assert pages[record_log_id] >= 2
    text = _pdf_text(preview.content)
    assert "Draft Project" in text
    assert "INS-DRAFT-906" in text
    assert "FAIL" in text

    official = client.post(f"/api/v1/records/{record['id']}/preview-pdf?kind=official", json={"project": "Draft Project"}, headers=headers)
    assert official.status_code == 200
    assert "Draft Project" in _pdf_text(official.content)

    bad = client.post(f"/api/v1/records/{record['id']}/preview-pdf", json={"log_overrides": {record_log_id: {"evaluation_status": "OK"}}}, headers=headers)
    assert bad.status_code == 422

    saved = client.get(f"/api/v1/records/{record['id']}").json()
    assert saved["project"] == "Saved Project"
    assert saved["items"][0]["result"] == "PASS"
    assert not saved["logs"][0]["metadata_snapshot"].get("attachment_overrides")
