import json
import tempfile
from pathlib import Path
from wika_report.config import AppConfig
from wika_report.file_processor import (
    get_unique_filepath,
    get_log_folder_name,
    process_single_csv,
    process_test_input,
)
from wika_report.models import (
    CustomMetadata,
    PhotoAttachment,
    TestInput,
    normalize_log_no,
)


def test_unique_filepath():
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)
        f1 = get_unique_filepath(target_dir, "test.csv", ".xlsx")
        f1.touch()
        assert f1.name == "test.xlsx"

        f2 = get_unique_filepath(target_dir, "test.csv", ".xlsx")
        assert f2.name != "test.xlsx"
        assert f2.name.startswith("test_")
        assert f2.suffix == ".xlsx"


def test_normalize_log_no():
    assert normalize_log_no("014FED") == "014FED"
    assert normalize_log_no("Log_014FED") == "014FED"
    assert normalize_log_no("log_021FED ") == "021FED"
    assert normalize_log_no("LOG_022-A") == "022-A"
    assert normalize_log_no("014/FED:2") == "014_FED_2"
    assert normalize_log_no("N/A", fallback_name="fallback") == "fallback"
    assert normalize_log_no("", fallback_name="fallback") == "fallback"
    assert normalize_log_no(None, fallback_name="fallback") == "fallback"


def test_get_log_folder_name():
    meta1 = CustomMetadata(log_no="014FED")
    assert get_log_folder_name(meta1, "fallback") == "014FED"

    meta2 = CustomMetadata(log_no="014/FED:2")
    assert get_log_folder_name(meta2, "fallback") == "014_FED_2"

    meta3 = CustomMetadata(log_no="N/A")
    assert get_log_folder_name(meta3, "fallback_name") == "fallback_name"

    assert get_log_folder_name(None, "fallback_name") == "fallback_name"


def test_process_single_csv_log_folder():
    sample_path = Path(__file__).parent.parent / "samples" / "sample_1_semicolon_comma.csv"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        input_dir = tmp / "input"
        output_dir = tmp / "output"
        processed_dir = tmp / "processed"
        failed_dir = tmp / "failed"
        input_dir.mkdir()

        test_file = input_dir / "test_log.csv"
        test_file.write_text(sample_path.read_text(encoding="utf-8"), encoding="utf-8")

        custom_meta = CustomMetadata(log_no="014FED")
        config = AppConfig()

        res = process_single_csv(
            file_path=test_file,
            output_dir=output_dir,
            processed_dir=processed_dir,
            failed_dir=failed_dir,
            config=config,
            override_custom_meta=custom_meta
        )

        assert res.success
        assert (output_dir / "014FED").exists()
        assert (output_dir / "014FED" / "test_log.png").exists()
        assert (output_dir / "014FED" / "test_log.xlsx").exists()
        assert (output_dir / "014FED" / "test_log.txt").exists()
        assert (output_dir / "014FED" / "manifest.json").exists()


def test_process_test_input_atomic_manifest_and_sha256():
    sample_path = Path(__file__).parent.parent / "samples" / "sample_1_semicolon_comma.csv"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_base = tmp / "output"
        test_file = tmp / "sample_input.csv"
        test_file.write_text(sample_path.read_text(encoding="utf-8"), encoding="utf-8")

        test_input = TestInput(
            csv_path=test_file,
            log_no="Log_099XYZ",
            test_pressure="25 bar",
            system="Hydraulic System 1",
            ins_no="INS-2026-001",
            operator="Matti Meikäläinen",
            bundle_numbers=["B-100", "B-101"],
            pipe_numbers=["P-01", "P-02", "P-03"],
            project="Project Arctic",
            note="Test run note"
        )
        config = AppConfig()

        build_res = process_test_input(test_input, output_base_dir=out_base, config=config)

        assert build_res.success
        assert build_res.log_no == "099XYZ"
        assert build_res.revision_dir == out_base / "099XYZ"
        assert build_res.manifest_path.exists()
        assert build_res.source_csv_path.exists()

        # Check manifest contents
        manifest_data = json.loads(build_res.manifest_path.read_text(encoding="utf-8"))
        assert manifest_data["manifest_version"] == "1.0"
        assert manifest_data["log_no"] == "099XYZ"
        assert manifest_data["created_by"] == "Matti Meikäläinen"
        assert manifest_data["metadata"]["system"] == "Hydraulic System 1"
        assert manifest_data["metadata"]["bundle_numbers"] == ["B-100", "B-101"]
        assert manifest_data["metadata"]["pipe_numbers"] == ["P-01", "P-02", "P-03"]

        # Check artifacts and sha256 checksums
        artifacts = manifest_data["artifacts"]
        assert len(artifacts) >= 4  # source_csv, graph_png, excel_xlsx, text_txt
        for art in artifacts:
            assert "sha256" in art and len(art["sha256"]) == 64
            assert "size_bytes" in art and art["size_bytes"] > 0
            assert (build_res.revision_dir / art["relative_path"]).exists()


def test_process_test_input_no_overwrite_preserves_revision_history():
    sample_path = Path(__file__).parent.parent / "samples" / "sample_1_semicolon_comma.csv"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_base = tmp / "output"
        test_file = tmp / "sample_input.csv"
        test_file.write_text(sample_path.read_text(encoding="utf-8"), encoding="utf-8")

        config = AppConfig()

        # Run 1: initial revision
        t1 = TestInput(csv_path=test_file, log_no="042REV", operator="Operator 1")
        res1 = process_test_input(t1, output_base_dir=out_base, config=config)
        assert res1.success
        assert res1.manifest_path.exists()

        # Run 2: second run for same log should preserve previous manifest in revisions/
        t2 = TestInput(csv_path=test_file, log_no="042REV", operator="Operator 2")
        res2 = process_test_input(t2, output_base_dir=out_base, config=config)
        assert res2.success

        revisions_dir = out_base / "042REV" / "revisions"
        assert revisions_dir.exists()
        saved_manifests = list(revisions_dir.glob("*/manifest.json"))
        assert len(saved_manifests) >= 1



