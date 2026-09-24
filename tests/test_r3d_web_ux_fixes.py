"""Regression guards for the approved R3 web usability fixes."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.api.database import Base
from services.api.models import Bundle, Pipe, PlannedTestList, PlannedTestPipe, PressureTest, TestRevision
from services.api.routes.planned_tests import _pipecloud_source_data, canonicalize_pipecloud_source_data
from services.api.routes.tests import PtrSourceResolveRequest, resolve_ptr_sources


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web" / "src"


def test_new_test_modal_does_not_close_when_backdrop_is_clicked():
    source = (WEB / "components" / "NewTestModal.tsx").read_text(encoding="utf-8")
    assert '<div className="modal-overlay">' in source
    assert '<div className="modal-overlay" onClick={onClose}>' not in source
    assert 'className="modal-close-btn" onClick={onClose}' in source


def test_pressure_test_filters_are_sent_to_the_server():
    source = (WEB / "api.ts").read_text(encoding="utf-8")
    for parameter in ("log_no", "test_date", "operator", "bundle", "pipe"):
        assert f"params.append('{parameter}'" in source

    route = (ROOT / "services" / "api" / "routes" / "tests.py").read_text(encoding="utf-8")
    for parameter in ("log_no:", "test_date:", "operator:", "bundle:", "pipe:"):
        assert parameter in route


def test_pipe_picker_places_bundles_first_and_supports_range_and_select_all():
    source = (WEB / "components" / "NewRecordModal.tsx").read_text(encoding="utf-8")
    assert source.index("availableBundleNumbers.map") < source.index("availablePipeNumbers.map((pipeNumber, index)")
    assert "event.shiftKey" in source
    assert "availablePipeNumbers.slice(start, end + 1)" in source
    assert "selectAllAvailablePipes" in source
    assert "btn_select_all_pipes" in source


def test_every_new_label_exists_in_all_three_languages():
    source = (WEB / "i18n.ts").read_text(encoding="utf-8")
    keys = (
        "btn_select_all_pipes",
        "pipe_bundles_title",
        "pipe_numbers_title",
        "pipe_bundle_prefix",
        "pipe_shift_hint",
        "filter_recent",
        "advanced_filters",
        "filter_log_no",
        "filter_date",
        "filter_operator",
        "filter_bundle",
        "filter_pipe",
        "filter_clear",
    )
    for key in keys:
        assert source.count(f"{key}:") == 3


def test_pipecloud_row_maps_to_the_actual_pipecloud_columns():
    raw = "Fit 900001/7 DRAW9001 07 456700 B Cooling water W 12 pcs 24.57 RAL 5019, C3 PS-1A 50 2.9 FE 6 2026-09-25 2026-09-26"
    source = _pipecloud_source_data(raw)
    assert source["drawing"] == "DRAW9001"
    assert source["spool_number"] == "07"
    assert source["order_number"] == "456700"
    assert source["revision"] == "B"
    assert source["pipeline"] == "Cooling water"
    assert source["pt"] == "W"
    assert source["wp"] == "12 pcs"
    assert source["kg"] == "24.57"
    assert source["treatment"] == "RAL 5019, C3 PS-1A"
    assert source["material"] == "FE"
    assert source["bundles"] == "6"
    assert "product" not in source


def test_legacy_shifted_source_data_is_repaired_from_raw_source():
    raw = "Fit 900001/7 DRAW9001 07 456700 B Cooling water W 12 pcs 24.57 RAL 5019, C3 PS-1A 50 2.9 FE 6 2026-09-25 2026-09-26"
    repaired = canonicalize_pipecloud_source_data({"raw_source": raw, "product": "wrong", "drawing": "wrong"})
    assert repaired["drawing"] == "DRAW9001"
    assert repaired["spool_number"] == "07"
    assert "product" not in repaired


def test_ptr_resolution_keeps_only_explicit_pipes_and_returns_repaired_metadata():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        first_test = PressureTest(id="test-1", log_no="LOG-1")
        first_revision = TestRevision(id="revision-1", pressure_test_id="test-1", revision_id="r1")
        second_test = PressureTest(id="test-2", log_no="LOG-2")
        second_revision = TestRevision(id="revision-2", pressure_test_id="test-2", revision_id="r2")
        plan = PlannedTestList(id="plan-1", name="Synthetic")
        raw = "Fit 900001/1 DRAW9001 01 456700 B Cooling water W 12 pcs 24.57 RAL 5019, C3 PS-1A 50 2.9 FE 6 2026-09-25 2026-09-26"
        db.add_all([
            first_test,
            first_revision,
            Pipe(id="pipe-1", test_revision_id="revision-1", pipe_number="900001/1"),
            Pipe(id="pipe-other-bundle", test_revision_id="revision-1", pipe_number="800001/9"),
            Bundle(id="bundle-1", test_revision_id="revision-1", bundle_number="900001"),
            second_test,
            second_revision,
            Pipe(id="pipe-2", test_revision_id="revision-2", pipe_number="900001/2"),
            Bundle(id="bundle-2", test_revision_id="revision-2", bundle_number="900001"),
            plan,
            PlannedTestPipe(
                id="planned-1",
                planned_test_list_id="plan-1",
                pipe_number="900001/1",
                bundle_number="900001",
                pipe_sort_key="1",
                source_data={"raw_source": raw, "drawing": "shifted"},
            ),
        ])
        db.commit()

        result = resolve_ptr_sources(PtrSourceResolveRequest(identifiers=["900001", "900001/1"]), db)
        assert len(result["matches"]) == 1
        assert result["matches"][0]["selected_pipe_numbers"] == ["900001/1"]
        assert result["matches"][0]["pipe_source_data"]["900001/1"]["drawing"] == "DRAW9001"
        assert result["matches"][0]["pipe_source_data"]["900001/1"]["spool_number"] == "01"
    finally:
        db.close()
