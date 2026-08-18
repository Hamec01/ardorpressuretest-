from datetime import datetime
from typing import Tuple
import numpy as np
import pandas as pd

from wika_report.models import CleaningStats, ColumnMapping
from wika_report.unit_converter import convert_series_to_bar


def parse_datetime_series(series: pd.Series) -> pd.Series:
    """Парсит серию строк в datetime с поддержкой различных европейских и ISO форматов."""
    # Замена запятых на точки в миллисекундах если есть
    s_clean = series.astype(str).str.strip()

    # Попытка стандартным pd.to_datetime (dayfirst=True для европейских дат)
    parsed = pd.to_datetime(s_clean, dayfirst=True, errors="coerce", format="mixed")
    return parsed


def clean_and_normalize_data(
    df: pd.DataFrame,
    mapping: ColumnMapping,
    input_unit: str,
    decimal_sep: str = ","
) -> Tuple[pd.DataFrame, CleaningStats]:
    """
    Выполняет очистку исходных данных:
    1. Преобразование давления в числа и конвертация в bar.
    2. Парсинг времени и расчёт дельты от начала (в секундах и минутах).
    3. Фильтрация NaN, дубликатов и битых строк.
    4. Сбор статистики очистки.
    """
    stats = CleaningStats(total_raw_rows=len(df))
    reasons = {}

    work_df = df.copy()

    # 1. Очистка давления
    if not mapping.pressure_col or mapping.pressure_col not in work_df.columns:
        raise ValueError(f"Столбец давления '{mapping.pressure_col}' не найден в данных.")

    raw_press = work_df[mapping.pressure_col].astype(str).str.strip()
    
    # Замена запятой на точку для конвертации во float
    if decimal_sep == ",":
        raw_press_clean = raw_press.str.replace(",", ".", regex=False)
    else:
        raw_press_clean = raw_press.str.replace(" ", "", regex=False)

    numeric_press = pd.to_numeric(raw_press_clean, errors="coerce")
    
    invalid_press_mask = numeric_press.isna() | np.isinf(numeric_press)
    if invalid_press_mask.sum() > 0:
        reasons["Некорректное или отсутствует значение давления"] = int(invalid_press_mask.sum())

    work_df["_raw_pressure"] = raw_press
    work_df["_numeric_pressure"] = numeric_press
    work_df["pressure_bar"] = convert_series_to_bar(numeric_press, input_unit)

    # 1.1 Очистка температуры
    if mapping.temperature_col and mapping.temperature_col in work_df.columns:
        raw_temp = work_df[mapping.temperature_col].astype(str).str.strip()
        if decimal_sep == ",":
            raw_temp_clean = raw_temp.str.replace(",", ".", regex=False)
        else:
            raw_temp_clean = raw_temp.str.replace(" ", "", regex=False)
        numeric_temp = pd.to_numeric(raw_temp_clean, errors="coerce")
        work_df["temperature_c"] = numeric_temp
    else:
        work_df["temperature_c"] = np.nan


    # 2. Очистка и нормализация времени
    if mapping.time_kind == "separate_date_time" and mapping.date_col and mapping.time_col:
        combined_time_str = work_df[mapping.date_col].astype(str).str.strip() + " " + work_df[mapping.time_col].astype(str).str.strip()
        work_df["_datetime"] = parse_datetime_series(combined_time_str)
        work_df["_time_raw_str"] = combined_time_str
    elif mapping.time_col and mapping.time_col in work_df.columns:
        raw_time_str = work_df[mapping.time_col].astype(str).str.strip()
        work_df["_time_raw_str"] = raw_time_str
        
        # Проверяем, являются ли значения чистыми секундами/числами
        numeric_time = pd.to_numeric(raw_time_str.str.replace(",", "."), errors="coerce")
        if numeric_time.notna().all() and (numeric_time.diff().dropna() >= 0).all():
            # Относительные секунды от начала
            work_df["_datetime"] = pd.NaT
            work_df["time_rel_sec"] = numeric_time - numeric_time.iloc[0]
            mapping.time_kind = "relative_sec"
        else:
            work_df["_datetime"] = parse_datetime_series(raw_time_str)
    else:
        # Индексный режим
        work_df["_datetime"] = pd.NaT
        work_df["_time_raw_str"] = work_df.index.astype(str)
        work_df["time_rel_sec"] = work_df.index.astype(float)
        mapping.time_kind = "index"

    # Маска некорректного времени (если ожидался datetime)
    if mapping.time_kind in ["datetime", "separate_date_time"]:
        invalid_time_mask = work_df["_datetime"].isna()
        if invalid_time_mask.sum() > 0:
            reasons["Некорректный или отсутствует формат времени/даты"] = int(invalid_time_mask.sum())
    else:
        invalid_time_mask = pd.Series(False, index=work_df.index)

    # Объединенная маска валидных строк
    valid_mask = (~invalid_press_mask) & (~invalid_time_mask)
    clean_df = work_df[valid_mask].copy()

    # Удаление полных дубликатов
    dup_mask = clean_df.duplicated(subset=["_time_raw_str", "_raw_pressure"], keep="first")
    if dup_mask.sum() > 0:
        reasons["Полные дубликаты строк"] = int(dup_mask.sum())
        clean_df = clean_df[~dup_mask].copy()

    # Сортировка по времени
    if mapping.time_kind in ["datetime", "separate_date_time"]:
        clean_df.sort_values(by="_datetime", inplace=True)
        clean_df.reset_index(drop=True, inplace=True)
        start_dt = clean_df["_datetime"].iloc[0]
        clean_df["time_rel_sec"] = (clean_df["_datetime"] - start_dt).dt.total_seconds()
    else:
        clean_df.reset_index(drop=True, inplace=True)

    clean_df["time_rel_min"] = clean_df["time_rel_sec"] / 60.0
    clean_df["point_idx"] = clean_df.index + 1

    stats.clean_rows = len(clean_df)
    stats.excluded_rows = stats.total_raw_rows - stats.clean_rows
    stats.exclusion_reasons = reasons

    return clean_df, stats
