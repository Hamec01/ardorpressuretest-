"""A synthetic lead-in changes only graph presentation, never the CSV or analysis."""
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from wika_report.config import AppConfig, GraphConfig, load_config
from wika_report.file_processor import process_test_input
from wika_report.graph_builder import zero_start_curve
from wika_report.models import TestInput
from wika_report.ptr_generator import render_ptr_graph

CSV = """Date;Time;Pressure [bar];Temperature [°C];
19.08.2026;10:00:00;15,20;21,5;
19.08.2026;10:15:00;15,18;21,4;
19.08.2026;10:30:00;15,16;21,3;
19.08.2026;10:45:00;15,14;21,2;
19.08.2026;11:00:00;15,12;21,1;
"""


@pytest.mark.parametrize("seconds", [10, 30, 50])
def test_rise_is_smooth_monotone_and_meets_the_first_reading(seconds):
    x, y = zero_start_curve(0, 15.2, GraphConfig(start_from_zero=True, zero_ramp_seconds=seconds))
    assert x[0] == pytest.approx(-seconds / 60)
    assert x[-1] == 0
    assert (y[0], y[-1]) == (0, 15.2)
    assert np.all(np.diff(x) > 0)
    assert np.all(np.diff(y) > 0)
    # Slope eases in and out; this is a curve rather than a jump or a straight line.
    dy = np.diff(y)
    assert dy[0] < dy[len(dy) // 2] / 10
    assert dy[-1] < dy[len(dy) // 2] / 10


@pytest.mark.parametrize("enabled,pressure", [(False, 15), (True, 0), (True, -1)])
def test_no_extra_segment_when_disabled_or_start_is_not_positive(enabled, pressure):
    x, y = zero_start_curve(0, pressure, GraphConfig(start_from_zero=enabled))
    assert len(x) == len(y) == 0


@pytest.mark.parametrize("seconds", [0, 9, 51, float("nan"), float("inf")])
def test_core_rejects_invalid_duration(seconds):
    with pytest.raises(ValueError, match="10 and 50"):
        zero_start_curve(0, 15, GraphConfig(start_from_zero=True, zero_ramp_seconds=seconds))


@pytest.fixture
def drawn_figures(monkeypatch):
    figures = []
    original = Figure.savefig

    def capture(fig, *args, **kwargs):
        figures.append(fig)
        return original(fig, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture)
    return figures


def test_processing_preserves_source_metrics_and_excel(tmp_path, drawn_figures):
    csv = tmp_path / "readings.csv"
    csv.write_text(CSV, encoding="utf-8")
    original_bytes = csv.read_bytes()
    config = AppConfig()
    manifests = []
    results = []
    for enabled in (False, True):
        result = process_test_input(
            TestInput(csv_path=csv, log_no=f"ZERO{int(enabled)}", graph_start_from_zero=enabled, graph_zero_ramp_seconds=50),
            tmp_path / "out", config,
        )
        assert result.success, result.error_message
        results.append(result)
        manifests.append(json.loads(Path(result.manifest_path).read_text(encoding="utf-8")))
        assert Path(result.source_csv_path).read_bytes() == original_bytes
    assert csv.read_bytes() == original_bytes
    assert manifests[0]["metrics"] == manifests[1]["metrics"]
    assert manifests[1]["metadata"]["graph_start_from_zero"] is True
    assert manifests[1]["metadata"]["graph_zero_ramp_seconds"] == 50
    assert config.graph.start_from_zero is False
    workbooks = [pd.read_excel(result.excel_path, sheet_name=None) for result in results]
    assert workbooks[0].keys() == workbooks[1].keys()
    # Compare the measurement sheet, excluding report metadata such as generation time.
    for sheet_name in ("Cleaned Data", "Raw Data"):
        pd.testing.assert_frame_equal(workbooks[0][sheet_name], workbooks[1][sheet_name])
    assert len(workbooks[1]["Cleaned Data"]) == 5
    baseline, with_ramp = [fig.axes[0] for fig in drawn_figures]
    actual = next(line for line in with_ramp.lines if line.get_label() == "Pressure / bar")
    assert list(actual.get_xdata()) == [0, 15, 30, 45, 60]
    assert list(actual.get_ydata()) == pytest.approx([15.2, 15.18, 15.16, 15.14, 15.12])
    ramp = next(line for line in with_ramp.lines if line.get_label().startswith("Added rise"))
    assert ramp.get_linestyle() == "-"
    assert "Not measured" in ramp.get_label()
    assert with_ramp.get_ylim()[0] == 0
    assert baseline.get_ylim()[0] > 0
    # Min and checkpoint annotations refer to the measured readings, not the lead-in.
    texts = [text.get_text() for text in with_ramp.texts]
    assert "Min: 15.120 bar" in texts
    assert "40 min: 15.140 bar" in texts


@pytest.mark.parametrize("stored,expected", [(None, False), (False, False), ("false", False), (True, True)])
def test_ptr_reuses_stored_setting_and_old_logs_keep_their_appearance(tmp_path, drawn_figures, stored, expected):
    csv = tmp_path / "readings.csv"
    csv.write_text(CSV, encoding="utf-8")
    metadata = {"graph_start_from_zero": stored, "graph_zero_ramp_seconds": 10}
    output = render_ptr_graph({"csv_path": str(csv), "metadata": metadata, "log_no": "ZERO"}, {}, tmp_path / "ptr.png")
    assert output and output.exists()
    labels = [line.get_label() for line in drawn_figures[-1].axes[0].lines]
    assert any(label.startswith("Added rise (10 s)") for label in labels) is expected


def test_config_round_trip(tmp_path):
    cfg = AppConfig()
    cfg.graph.start_from_zero = True
    cfg.graph.zero_ramp_seconds = 20
    path = tmp_path / "config.json"
    path.write_text(json.dumps(asdict(cfg)), encoding="utf-8")
    restored = load_config(path)
    assert restored.graph.start_from_zero is True
    assert restored.graph.zero_ramp_seconds == 20


@pytest.mark.usefixtures("signed_in_admin")
def test_web_draft_then_csv_and_invalid_duration(tmp_path):
    from fastapi.testclient import TestClient

    from services.api.database import Base, engine
    from services.api.main import app

    Base.metadata.create_all(bind=engine)
    try:
        client = TestClient(app)
        for value in ("9", "51", "nan", "inf", "bad"):
            response = client.post("/api/v1/process", data={"log_no": "INVALID", "graph_zero_ramp_seconds": value})
            assert response.status_code == 422, response.text
        fields = {"log_no": "ZEROWEB", "create_pdf": "false", "graph_start_from_zero": "true", "graph_zero_ramp_seconds": "50"}
        draft = client.post("/api/v1/process", data=fields)
        assert draft.status_code == 200, draft.text
        done = client.post("/api/v1/process", data=fields, files={"csv_file": ("synthetic.csv", CSV.encode(), "text/csv")})
        assert done.status_code == 200, done.text
        for response in (draft, done):
            metadata = next(r for r in response.json()["revisions"] if r["is_primary"])["metadata_json"]
            assert metadata["graph_start_from_zero"] is True
            assert metadata["graph_zero_ramp_seconds"] == 50
        default = client.post("/api/v1/process", data={"log_no": "ZERODEFAULT"})
        metadata = next(r for r in default.json()["revisions"] if r["is_primary"])["metadata_json"]
        assert metadata["graph_start_from_zero"] is False
        assert metadata["graph_zero_ramp_seconds"] == 30
    finally:
        Base.metadata.drop_all(bind=engine)
