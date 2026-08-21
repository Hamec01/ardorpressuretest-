import hashlib
import io
import pytest
from pathlib import Path
from wika_report.ptr_generator import (
    generate_ptr_pdf,
    generate_full_composite_ptr_pdf,
    estimate_composite_ptr_pages,
)


def test_official_ptr_pdf_single_page(tmp_path):
    record_data = {
        "record_number": "PTR-TEST-001",
        "ins_no": "Inspection 044",
        "project": "LNG Pipeline Project",
        "system": "Fuel Gas System",
        "design_pressure": "16 bar",
        "test_pressure": "24 bar",
        "test_medium": "Water",
        "duration_min": "60 min",
        "foreman_name": "Matti QC",
        "verification_code": "ARDOR-VRF-12345678-2026",
        "confirmed_at": "2026-08-20T10:00:00Z",
        "notes": "Single page test passed."
    }

    items_data = [
        {"item_no": i, "drawing_no": f"DWG-{i}", "pipe_number": f"PIPE-{1000 + i}", "log_no": "044-1", "result": "PASS"}
        for i in range(1, 5)
    ]

    out_file = tmp_path / "PTR_Single.pdf"
    pdf_bytes = generate_ptr_pdf(record_data, items_data, output_path=out_file)

    assert len(pdf_bytes) > 1000
    assert out_file.exists()
    assert pdf_bytes[:4] == b"%PDF"


def test_official_ptr_pdf_multipage_pagination(tmp_path):
    # 35 pipes should paginate cleanly across multiple pages
    record_data = {
        "record_number": "PTR-MULTI-035",
        "ins_no": "Inspection Multi",
        "project": "Large Terminal Plant",
        "system": "Hydraulic System",
        "design_pressure": "200 bar",
        "test_pressure": "300 bar",
        "test_medium": "Water",
        "duration_min": "60 min",
        "foreman_name": "Antti QC",
        "verification_code": "ARDOR-VRF-87654321-2026",
        "confirmed_at": "2026-08-20T11:00:00Z",
        "notes": "Large bundle test completed."
    }

    items_data = [
        {"item_no": i, "drawing_no": f"DWG-MAIN-{i // 10}", "pipe_number": f"P-{10000 + i}", "log_no": f"044-{(i % 3) + 1}", "result": "PASS"}
        for i in range(1, 36)
    ]

    out_file = tmp_path / "PTR_Multi.pdf"
    pdf_bytes = generate_ptr_pdf(record_data, items_data, output_path=out_file)

    assert len(pdf_bytes) > 2000
    assert out_file.exists()
    assert pdf_bytes[:4] == b"%PDF"

    # Verify SHA-256 calculation
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    assert len(sha256) == 64


def test_full_composite_ptr_pdf(tmp_path):
    record_data = {
        "record_number": "PTR-COMPOSITE-100",
        "ins_no": "Inspection Composite",
        "project": "Terminal Upgrade",
        "system": "High Pressure Steam",
        "design_pressure": "40 bar",
        "test_pressure": "60 bar",
        "test_medium": "Water",
        "duration_min": "60 min",
        "foreman_name": "Mikko Foreman",
        "verification_code": "ARDOR-VRF-AAAA-2026"
    }

    items_data = [
        {"item_no": 1, "drawing_no": "DWG-001", "pipe_number": "PIPE-9001", "log_no": "044-1", "result": "PASS"},
        {"item_no": 2, "drawing_no": "DWG-001", "pipe_number": "PIPE-9002", "log_no": "044-1", "result": "PASS"},
    ]

    # Create a dummy CSV for measurement table
    dummy_csv = tmp_path / "test_data.csv"
    with open(dummy_csv, "w", encoding="utf-8") as f:
        f.write("Time;Pressure;Temperature\n")
        for m in range(60):
            f.write(f"12.08.2026 10:{m:02d}:00;60.{m % 5};21.5\n")

    logs_data = [
        {
            "log_no": "044-1",
            "revision_id": "20260820_100000",
            "metadata": {
                "test_pressure": "60.0 bar",
                "system": "High Pressure Steam",
                "project": "Terminal Upgrade",
                "operator": "Pekka Operator",
                "pipe_numbers": ["PIPE-9001", "PIPE-9002"]
            },
            "metrics": {
                "start_time": "2026-08-20T10:00:00Z",
                "end_time": "2026-08-20T11:00:00Z",
                "duration_formatted": "01:00:00",
                "min_pressure_bar": 59.8,
                "max_pressure_bar": 60.5,
                "mean_pressure_bar": 60.1,
                "total_delta_bar": 0.2,
                "evaluation_status": "PASS"
            },
            "selected_pipe_numbers": ["PIPE-9001", "PIPE-9002"],
            "include_measurement_table": True,
            "csv_path": str(dummy_csv),
            "artifacts": [
                {"name": "test_data.csv", "file_type": "source_csv", "file_path": str(dummy_csv), "sha256": "dummy_sha"}
            ]
        }
    ]

    out_file = tmp_path / "PTR_Full_Composite.pdf"
    pdf_bytes = generate_full_composite_ptr_pdf(record_data, items_data, logs_data, output_path=out_file)

    assert len(pdf_bytes) > 2500
    assert out_file.exists()
    assert pdf_bytes[:4] == b"%PDF"


def test_estimate_composite_ptr_pages():
    record_data = {"record_number": "PTR-EST-1"}
    items_data = [{"item_no": i} for i in range(1, 25)]  # 24 items -> 1 + ceil((24-7)/14) = 1 + 2 = 3 pages
    logs_data = [
        {
            "log_no": "044-1",
            "include_measurement_table": True,
            "artifacts": [
                {"name": "p1.jpg", "file_type": "photo", "category": "gauge", "is_included_in_pdf": True},
                {"name": "p2.jpg", "file_type": "photo", "category": "pipe", "is_included_in_pdf": True}
            ]
        }
    ]

    estimates = estimate_composite_ptr_pages(record_data, items_data, logs_data)
    assert estimates["official_pages"] == 3
    assert estimates["full_total_pages"] >= 3
    assert len(estimates["log_estimates"]) == 1
    assert estimates["log_estimates"][0]["log_no"] == "044-1"


def test_cyrillic_and_unicode_composite_pdf(tmp_path):
    """Проверяет корректность генерации PDF с русскими/финскими буквами и спецсимволами."""
    record_data = {
        "record_number": "PTR-CYRILLIC-2026",
        "ins_no": "Инспекция 044 (Inspection)",
        "project": "Проект ARDOR Terminal — Установка #3",
        "system": "Топливная система (Fuel Gas)",
        "design_pressure": "16 bar",
        "test_pressure": "24 bar",
        "test_medium": "Вода (Water)",
        "duration_min": "60 мин",
        "foreman_name": "Матти Мейкаляйнен",
        "notes": "Опрессовка успешно завершена. Падение давления отсутствует — PASS."
    }

    items_data = [
        {"item_no": 1, "drawing_no": "Чертёж-01", "spool_no": "Катушка-А", "pipe_number": "ТРУБА-101", "log_no": "044-1", "result": "PASS", "notes": "60 мин"}
    ]

    logs_data = [
        {
            "log_no": "044-1",
            "revision_id": "rev_20260820",
            "metadata": {
                "system": "Топливная система",
                "project": "Проект ARDOR",
                "operator": "Иван Оператор",
                "note": "Испытание проведено успешно."
            },
            "metrics": {
                "min_pressure_bar": 24.1,
                "max_pressure_bar": 24.2,
                "mean_pressure_bar": 24.15,
                "duration_formatted": "60 мин",
                "evaluation_status": "PASS"
            },
            "selected_pipe_numbers": ["ТРУБА-101"],
            "include_measurement_table": False,
            "artifacts": []
        }
    ]

    out_file = tmp_path / "PTR_Cyrillic.pdf"
    pdf_bytes = generate_full_composite_ptr_pdf(record_data, items_data, logs_data, output_path=out_file)

    assert len(pdf_bytes) > 1000
    assert out_file.exists()
    assert pdf_bytes[:4] == b"%PDF"

