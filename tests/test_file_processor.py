import tempfile
from pathlib import Path
from wika_report.file_processor import get_unique_filepath, get_log_folder_name
from wika_report.models import CustomMetadata


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


def test_get_log_folder_name():
    meta1 = CustomMetadata(log_no="014FED")
    assert get_log_folder_name(meta1, "fallback") == "014FED"

    meta2 = CustomMetadata(log_no="014/FED:2")
    assert get_log_folder_name(meta2, "fallback") == "014_FED_2"

    meta3 = CustomMetadata(log_no="N/A")
    assert get_log_folder_name(meta3, "fallback_name") == "fallback_name"

    assert get_log_folder_name(None, "fallback_name") == "fallback_name"


def test_process_single_csv_log_folder():
    from wika_report.config import AppConfig
    from wika_report.file_processor import process_single_csv

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


