import tempfile
from pathlib import Path
import pytest
from wika_report.csv_reader import detect_delimiter_and_header, detect_encoding, read_wika_csv


def test_detect_delimiter_and_header_semicolon():
    lines = [
        "Timestamp;Pressure / bar;Temp",
        "01.08.2026 10:00:00;10,500;22,0",
        "01.08.2026 10:01:00;10,520;22,1"
    ]
    delim, header_idx, dec_sep = detect_delimiter_and_header(lines)
    assert delim == ";"
    assert header_idx == 0
    assert dec_sep == ","


def test_detect_delimiter_and_header_comma_dot():
    lines = [
        "Time,Pressure (psi),Temp",
        "2026-08-01 10:00:00,100.50,22.0",
        "2026-08-01 10:01:00,100.70,22.1"
    ]
    delim, header_idx, dec_sep = detect_delimiter_and_header(lines)
    assert delim == ","
    assert header_idx == 0
    assert dec_sep == "."


def test_read_wika_csv_preheader():
    content = (
        "# Device: CPG1500\n"
        "# Serial No: 12345\n"
        "Timestamp;Pressure / bar\n"
        "01.08.2026 10:00:00;15,50\n"
        "01.08.2026 10:01:00;15,55\n"
    )
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", encoding="utf-8", delete=False) as tf:
        tf.write(content)
        temp_path = Path(tf.name)

    try:
        df, meta = read_wika_csv(temp_path)
        assert meta.delimiter == ";"
        assert meta.header_line_idx == 2
        assert meta.detected_unit == "bar"
        assert meta.device_info.get("Device") == "CPG1500"
        assert len(df) == 2
    finally:
        temp_path.unlink(missing_ok=True)
