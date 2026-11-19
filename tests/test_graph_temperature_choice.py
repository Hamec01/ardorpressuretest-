"""Per-log graph choices: temperature curve on/off, hidden header lines; and the 40-minute mark."""
import json
from pathlib import Path

import pytest

from wika_report import file_processor
from wika_report.config import AppConfig
from wika_report.file_processor import normalize_hidden_header_fields, process_test_input, render_graph_png
from wika_report.graph_builder import checkpoint_index
from wika_report.models import TestInput

CSV_WITH_TEMPERATURE = """Date;Time;Pressure [bar];Temperature [°C];
19.08.2026;10:00:00;15,20;21,5;
19.08.2026;10:15:00;15,18;21,4;
19.08.2026;10:30:00;15,16;21,3;
19.08.2026;10:45:00;15,14;21,2;
19.08.2026;11:00:00;15,12;21,1;
"""


drawn_header_choices = []


@pytest.fixture
def drawn_temperature_flags(monkeypatch):
    drawn_header_choices.clear()
    """Record the plot_temperature value every graph is drawn with."""
    flags = []
    real_build = file_processor.build_pressure_graph

    def spy(*args, **kwargs):
        flags.append(kwargs["graph_cfg"].plot_temperature)
        drawn_header_choices.append(list(kwargs["graph_cfg"].hidden_header_fields))
        return real_build(*args, **kwargs)

    monkeypatch.setattr(file_processor, "build_pressure_graph", spy)
    return flags


def _process(tmp_path: Path, plot_temperature, config: AppConfig = None):
    csv_path = tmp_path / "Log_014FED.csv"
    csv_path.write_text(CSV_WITH_TEMPERATURE, encoding="utf-8")
    result = process_test_input(
        TestInput(csv_path=csv_path, log_no="014FED", plot_temperature=plot_temperature),
        output_base_dir=tmp_path / "out",
        config=config or AppConfig(),
    )
    assert result.success, result.error_message
    return json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))


@pytest.mark.parametrize("choice", [True, False])
def test_graph_follows_the_choice_and_the_manifest_records_it(tmp_path, drawn_temperature_flags, choice):
    manifest = _process(tmp_path, choice)
    assert drawn_temperature_flags == [choice]
    assert manifest["metadata"]["plot_temperature"] is choice


def test_without_a_choice_the_config_setting_is_kept(tmp_path, drawn_temperature_flags):
    config = AppConfig()
    config.graph.plot_temperature = False
    manifest = _process(tmp_path, None, config)
    assert drawn_temperature_flags == [False]
    assert manifest["metadata"]["plot_temperature"] is False
    assert config.graph.plot_temperature is False


def test_choice_does_not_change_the_shared_config(tmp_path, drawn_temperature_flags):
    config = AppConfig()
    _process(tmp_path, False, config)
    assert config.graph.plot_temperature is True


@pytest.mark.parametrize(
    "stored, expected",
    [(False, False), (True, True), ("false", False), (None, True)],
)
def test_ptr_copy_of_the_graph_uses_the_stored_choice(tmp_path, drawn_temperature_flags, stored, expected):
    csv_path = tmp_path / "Log_014FED.csv"
    csv_path.write_text(CSV_WITH_TEMPERATURE, encoding="utf-8")
    metadata = {"log_no": "014FED"}
    if stored is not None:
        metadata["plot_temperature"] = stored
    render_graph_png(csv_path, metadata, tmp_path / "graph.png")
    assert drawn_temperature_flags == [expected]


def _primary_metadata(test_json: dict) -> dict:
    primary = next(r for r in test_json["revisions"] if r["is_primary"])
    return primary["metadata_json"]


@pytest.mark.usefixtures("signed_in_admin")
def test_web_form_choice_reaches_the_revision_and_the_draft():
    """API: the form field is stored on the draft and on the revision made from the CSV."""
    from fastapi.testclient import TestClient
    from services.api.database import Base, engine
    from services.api.main import app

    Base.metadata.create_all(bind=engine)
    try:
        client = TestClient(app)
        draft = client.post(
            "/api/v1/process",
            data={"log_no": "TEMP01", "create_pdf": "false", "plot_temperature": "false", "graph_hidden_fields": "note,ins_no"},
        )
        assert draft.status_code == 200, draft.text
        assert _primary_metadata(draft.json())["plot_temperature"] is False
        assert _primary_metadata(draft.json())["graph_hidden_fields"] == ["ins_no", "note"]

        sample = Path(__file__).parent.parent / "samples" / "sample_1_semicolon_comma.csv"
        with open(sample, "rb") as f:
            done = client.post(
                "/api/v1/process",
                data={"log_no": "TEMP01", "create_pdf": "false", "plot_temperature": "false"},
                files={"csv_file": ("sample_1.csv", f, "text/csv")},
            )
        assert done.status_code == 200, done.text
        assert _primary_metadata(done.json())["plot_temperature"] is False
        assert _primary_metadata(done.json())["graph_hidden_fields"] == []

        with open(sample, "rb") as f:
            default = client.post(
                "/api/v1/process",
                data={"log_no": "TEMP02", "create_pdf": "false"},
                files={"csv_file": ("sample_1.csv", f, "text/csv")},
            )
        assert default.status_code == 200, default.text
        assert _primary_metadata(default.json())["plot_temperature"] is True
    finally:
        Base.metadata.drop_all(bind=engine)


def test_hidden_header_fields_are_cleaned_and_stored(tmp_path, drawn_temperature_flags):
    csv_path = tmp_path / "Log_014FED.csv"
    csv_path.write_text(CSV_WITH_TEMPERATURE, encoding="utf-8")
    result = process_test_input(
        TestInput(csv_path=csv_path, log_no="014FED", graph_hidden_fields=["note", "bogus", "SYSTEM"]),
        output_base_dir=tmp_path / "out",
        config=AppConfig(),
    )
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["metadata"]["graph_hidden_fields"] == ["system", "note"]
    assert drawn_header_choices == [["system", "note"]]


def test_ptr_copy_of_the_graph_hides_the_stored_header_fields(tmp_path, drawn_temperature_flags):
    csv_path = tmp_path / "Log_014FED.csv"
    csv_path.write_text(CSV_WITH_TEMPERATURE, encoding="utf-8")
    render_graph_png(csv_path, {"log_no": "014FED", "graph_hidden_fields": ["ins_no", "project"]}, tmp_path / "g.png")
    render_graph_png(csv_path, {"log_no": "014FED"}, tmp_path / "old.png")
    assert drawn_header_choices == [["ins_no", "project"], []]


def test_normalize_hidden_header_fields_accepts_the_form_string():
    assert normalize_hidden_header_fields("note, project,,x") == ["project", "note"]
    assert normalize_hidden_header_fields("") == []
    assert normalize_hidden_header_fields(None) == []


def test_checkpoint_is_the_reading_closest_to_40_minutes():
    minutes = [0.0, 15.0, 30.0, 39.5, 41.0, 60.0]
    assert checkpoint_index(minutes, 40.0) == 3
    assert checkpoint_index([0.0, 10.0, 39.0], 40.0) is None  # test shorter than 40 min
    assert checkpoint_index(minutes, None) is None
