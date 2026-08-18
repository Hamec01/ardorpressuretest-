from datetime import datetime, timedelta
from typing import Optional
import numpy as np
import pandas as pd

from wika_report.config import AnalysisConfig
from wika_report.models import AnalysisResult, CleaningStats, HoldPeriodStats


def format_duration(seconds: float) -> str:
    """Форматирует длительность в секундах в строку ЧЧ:ММ:СС."""
    total_sec = int(round(seconds))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def analyze_data(
    df: pd.DataFrame,
    stats: CleaningStats,
    analysis_cfg: Optional[AnalysisConfig] = None
) -> AnalysisResult:
    """
    Вычисляет полную статистику и метрики давления по очищенному датасету.
    """
    if df.empty:
        raise ValueError("Датасет пуст после очистки, невозможно выполнить анализ.")

    res = AnalysisResult()
    res.total_raw_rows = stats.total_raw_rows
    res.valid_points_count = stats.clean_rows
    res.excluded_rows_count = stats.excluded_rows

    press = df["pressure_bar"].values
    times_sec = df["time_rel_sec"].values

    # Временные метрики
    if "_datetime" in df.columns and df["_datetime"].notna().any():
        valid_dt = df["_datetime"].dropna()
        res.start_time = valid_dt.iloc[0].to_pydatetime()
        res.end_time = valid_dt.iloc[-1].to_pydatetime()
        res.duration_seconds = (res.end_time - res.start_time).total_seconds()
    else:
        res.duration_seconds = float(times_sec[-1] - times_sec[0]) if len(times_sec) > 1 else 0.0

    res.duration_formatted = format_duration(res.duration_seconds)

    # Статистика давления в bar
    res.start_pressure_bar = float(press[0])
    res.end_pressure_bar = float(press[-1])
    res.min_pressure_bar = float(np.min(press))
    res.max_pressure_bar = float(np.max(press))
    res.mean_pressure_bar = float(np.mean(press))
    res.median_pressure_bar = float(np.median(press))
    res.std_pressure_bar = float(np.std(press, ddof=1)) if len(press) > 1 else 0.0

    res.total_delta_bar = res.end_pressure_bar - res.start_pressure_bar
    res.range_bar = res.max_pressure_bar - res.min_pressure_bar

    # Момент достижения максимального давления
    max_idx = int(np.argmax(press))
    if "_datetime" in df.columns and pd.notna(df["_datetime"].iloc[max_idx]):
        res.max_pressure_time_str = df["_datetime"].iloc[max_idx].strftime("%Y-%m-%d %H:%M:%S")
    else:
        res.max_pressure_time_str = f"{df['time_rel_min'].iloc[max_idx]:.2f} мин"

    # Сбор метрик температуры
    if "temperature_c" in df.columns and df["temperature_c"].notna().any():
        res.has_temperature = True
        temps = df["temperature_c"].dropna().values
        res.min_temp = float(np.min(temps))
        res.max_temp = float(np.max(temps))

    # Скорости изменения давления (bar/мин)

    if len(press) > 1:
        dp = np.diff(press)
        dt_min = np.diff(df["time_rel_min"].values)
        # Фильтрация нулевых дельт по времени
        valid_dt_mask = dt_min > 1e-6
        if valid_dt_mask.any():
            rates = dp[valid_dt_mask] / dt_min[valid_dt_mask]
            res.max_rise_rate_bar_per_min = float(np.max(rates)) if (rates > 0).any() else 0.0
            res.max_drop_rate_bar_per_min = float(np.abs(np.min(rates))) if (rates < 0).any() else 0.0

    # Анализ участка выдержки
    if analysis_cfg and (analysis_cfg.create_pass_fail_result or analysis_cfg.hold_start_time_minutes is not None):
        res.hold_stats = analyze_hold_period(df, analysis_cfg)
    else:
        res.hold_stats = HoldPeriodStats(enabled=False, status="Не оценивалось")

    return res


def analyze_hold_period(df: pd.DataFrame, cfg: AnalysisConfig) -> HoldPeriodStats:
    """Анализирует участок выдержки высокого давления по заданным критериям."""
    hold = HoldPeriodStats(
        enabled=True,
        hold_start_min=cfg.hold_start_time_minutes,
        hold_end_min=cfg.hold_end_time_minutes,
        test_pressure_bar=cfg.test_pressure_bar,
        lower_limit_bar=cfg.lower_limit_bar,
        upper_limit_bar=cfg.upper_limit_bar,
        allowed_drop_bar=cfg.allowed_drop_bar,
    )

    times_min = df["time_rel_min"].values
    
    start_m = cfg.hold_start_time_minutes if cfg.hold_start_time_minutes is not None else 0.0
    end_m = cfg.hold_end_time_minutes if cfg.hold_end_time_minutes is not None else float(times_min[-1])

    mask = (times_min >= start_m) & (times_min <= end_m)
    hold_df = df[mask]

    if hold_df.empty:
        hold.status = "FAIL"
        hold.fail_reasons.append(f"Нет данных на участке выдержки от {start_m:.1f} до {end_m:.1f} мин")
        return hold

    hold_press = hold_df["pressure_bar"].values
    hold.min_pressure = float(np.min(hold_press))
    hold.max_pressure = float(np.max(hold_press))
    hold.mean_pressure = float(np.mean(hold_press))
    hold.drop_bar = float(hold_press[0] - hold_press[-1])

    # Проверка условий PASS/FAIL
    fail_reasons = []

    if cfg.lower_limit_bar is not None and hold.min_pressure < cfg.lower_limit_bar:
        fail_reasons.append(
            f"Минимальное давление на выдержке ({hold.min_pressure:.3f} bar) ниже нормы ({cfg.lower_limit_bar:.3f} bar)"
        )

    if cfg.upper_limit_bar is not None and hold.max_pressure > cfg.upper_limit_bar:
        fail_reasons.append(
            f"Максимальное давление на выдержке ({hold.max_pressure:.3f} bar) выше нормы ({cfg.upper_limit_bar:.3f} bar)"
        )

    if cfg.allowed_drop_bar is not None and hold.drop_bar > cfg.allowed_drop_bar:
        fail_reasons.append(
            f"Падение давления ({hold.drop_bar:.3f} bar) превышает допустимое ({cfg.allowed_drop_bar:.3f} bar)"
        )

    if cfg.create_pass_fail_result:
        if fail_reasons:
            hold.status = "FAIL"
            hold.fail_reasons = fail_reasons
        else:
            hold.status = "PASS"
    else:
        hold.status = "Не оценивалось"

    return hold
