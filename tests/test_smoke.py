import tempfile
from pathlib import Path
from wika_report.config import AppConfig
from wika_report.file_processor import process_single_csv
from wika_report.logging_setup import setup_logging


def test_smoke_pipeline():
    sample_path = Path(__file__).parent.parent / "samples" / "sample_1_semicolon_comma.csv"
    assert sample_path.exists(), "Синтетический sample_1_semicolon_comma.csv должен существовать."

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        processed_dir = tmp_path / "processed"
        failed_dir = tmp_path / "failed"

        input_dir.mkdir()
        test_file = input_dir / sample_path.name
        test_file.write_text(sample_path.read_text(encoding="utf-8"), encoding="utf-8")

        logger = setup_logging(output_dir / "logs")
        config = AppConfig()

        try:
            res = process_single_csv(
                file_path=test_file,
                output_dir=output_dir,
                processed_dir=processed_dir,
                failed_dir=failed_dir,
                config=config
            )

            assert res.success, f"Обработка sample завершилась с ошибкой: {res.error_message}"
            assert res.graph_path and res.graph_path.exists(), "PNG график должен быть создан"
            assert res.excel_path and res.excel_path.exists(), "Excel XLSX отчёт должен быть создан"
            assert res.report_path and res.report_path.exists(), "Текстовый отчёт должен быть создан"
            assert (output_dir / "logs" / "app.log").exists(), "Файл логов app.log должен быть создан"
        finally:
            from wika_report.logging_setup import close_logging
            close_logging(logger)

