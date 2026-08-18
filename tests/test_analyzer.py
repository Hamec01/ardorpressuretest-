import pandas as pd
import pytest
from wika_report.analyzer import analyze_data
from wika_report.config import AnalysisConfig
from wika_report.models import CleaningStats


def test_analyzer_basic():
    df = pd.DataFrame({
        "time_rel_sec": [0.0, 60.0, 120.0],
        "time_rel_min": [0.0, 1.0, 2.0],
        "pressure_bar": [10.0, 12.0, 11.0]
    })
    stats = CleaningStats(total_raw_rows=3, clean_rows=3, excluded_rows=0)

    res = analyze_data(df, stats)
    assert res.start_pressure_bar == 10.0
    assert res.end_pressure_bar == 11.0
    assert res.min_pressure_bar == 10.0
    assert res.max_pressure_bar == 12.0
    assert pytest.approx(res.mean_pressure_bar, 0.01) == 11.0
    assert res.duration_seconds == 120.0
    assert res.duration_formatted == "00:02:00"
    assert res.hold_stats.status == "Не оценивалось"


def test_analyzer_pass_fail():
    df = pd.DataFrame({
        "time_rel_sec": [0.0, 60.0, 120.0, 180.0],
        "time_rel_min": [0.0, 1.0, 2.0, 3.0],
        "pressure_bar": [10.0, 20.0, 19.8, 19.5]
    })
    stats = CleaningStats(total_raw_rows=4, clean_rows=4, excluded_rows=0)
    cfg = AnalysisConfig(
        test_pressure_bar=20.0,
        lower_limit_bar=18.0,
        upper_limit_bar=22.0,
        hold_start_time_minutes=1.0,
        hold_end_time_minutes=3.0,
        allowed_drop_bar=1.0,
        create_pass_fail_result=True
    )

    res = analyze_data(df, stats, cfg)
    assert res.hold_stats.status == "PASS"
    assert len(res.hold_stats.fail_reasons) == 0
