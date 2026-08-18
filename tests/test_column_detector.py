import pandas as pd
from wika_report.column_detector import detect_columns


def test_detect_columns_german():
    df = pd.DataFrame(columns=["Zeit", "Messwert / bar", "Temperatur"])
    mapping = detect_columns(df)
    assert mapping.time_col == "Zeit"
    assert mapping.pressure_col == "Messwert / bar"
    assert mapping.confidence > 0.9


def test_detect_columns_separate_date_time():
    df = pd.DataFrame(columns=["Date", "Time", "Pressure / psi"])
    mapping = detect_columns(df)
    assert mapping.date_col == "Date"
    assert mapping.time_col == "Time"
    assert mapping.pressure_col == "Pressure / psi"
    assert mapping.time_kind == "separate_date_time"


def test_detect_columns_finnish():
    df = pd.DataFrame(columns=["Aika", "Paine", "Lämpötila"])
    mapping = detect_columns(df)
    assert mapping.time_col == "Aika"
    assert mapping.pressure_col == "Paine"
