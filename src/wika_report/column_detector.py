import re
from typing import List, Optional, Tuple
import pandas as pd

from wika_report.models import ColumnMapping
from wika_report.unit_converter import is_supported_unit


TIME_KEYWORDS = [
    "timestamp", "measurement time", "date time", "datetime",
    "time stamp", "elapsed time", "duration", "measurementtime",
    "время", "дата и время", "zeit", "aika", "time", "datum",
    "päivämäärä", "seconds", "sec", "s"
]

DATE_KEYWORDS = ["date", "datum", "päivämäärä", "дата"]

PRESSURE_KEYWORDS = [
    "pressure value", "measured value", "pressure", "measurement",
    "reading", "value", "druck", "messwert", "paine", "mittausarvo",
    "давление", "измерение"
]

PRESSURE_EXCLUDE_KEYWORDS = ["min", "max", "average", "avg", "temp", "temperature", "мин", "макс", "температура"]


def normalize_col_name(col: str) -> str:
    """Нормализует имя столбца: нижний регистр, удаление спецсимволов."""
    c = col.lower().strip()
    c = re.sub(r"[\/\(\)\[\]\_\-\:\,\.]", " ", c)
    return re.sub(r"\s+", " ", c).strip()


def detect_columns(df: pd.DataFrame) -> ColumnMapping:
    """
    Автоматически находит столбцы времени и давления в DataFrame.
    """
    mapping = ColumnMapping()
    cols = list(df.columns)
    normalized_cols = [normalize_col_name(c) for c in cols]

    time_col: Optional[str] = None
    date_col: Optional[str] = None
    pressure_col: Optional[str] = None
    unit_col: Optional[str] = None

    # 1. Поиск отдельной колонки Unit (если есть)
    for orig, norm in zip(cols, normalized_cols):
        if norm in ["unit", "einheit", "единица"]:
            unit_col = orig
            break

    # 2. Поиск колонок времени
    # Сначала проверяем на раздельные Date и Time
    found_date = None
    found_time = None
    for orig, norm in zip(cols, normalized_cols):
        if norm in DATE_KEYWORDS or any(dk == norm for dk in DATE_KEYWORDS):
            found_date = orig
        elif norm == "time" or norm == "время" or norm == "zeit" or norm == "aika":
            found_time = orig

    if found_date and found_time and found_date != found_time:
        date_col = found_date
        time_col = found_time
        mapping.time_kind = "separate_date_time"
        mapping.notes.append(f"Обнаружены раздельные столбцы даты ('{found_date}') и времени ('{found_time}')")
    else:
        # Ищем совмещённый timestamp или время
        best_time_score = -1
        for orig, norm in zip(cols, normalized_cols):
            score = 0
            for tk in TIME_KEYWORDS:
                if norm == tk:
                    score += 20
                elif norm.startswith(tk):
                    score += 15
                elif tk in norm:
                    score += 10

            if score > best_time_score and score > 0:
                best_time_score = score
                time_col = orig

        if time_col:
            mapping.notes.append(f"Найден столбец времени/даты: '{time_col}'")

    # 3. Поиск столбца давления
    best_press_score = -1
    for orig, norm in zip(cols, normalized_cols):
        # Пропустить столбцы Min / Max / Temp, если есть основной столбец
        if any(ex in norm for ex in PRESSURE_EXCLUDE_KEYWORDS):
            continue

        score = 0
        for pk in PRESSURE_KEYWORDS:
            if norm == pk:
                score += 30
            elif norm.startswith(pk):
                score += 20
            elif pk in norm:
                score += 10

        # Поиск совпадений по единицам в названии столбца (например "pressure / bar")
        words = norm.split()
        for w in words:
            if is_supported_unit(w):
                score += 15

        if score > best_press_score and score > 0:
            best_press_score = score
            pressure_col = orig

    # Фолбэк для давления: если пропущен из-за слов min/max, но другого нет
    if not pressure_col:
        for orig, norm in zip(cols, normalized_cols):
            if any(pk in norm for pk in PRESSURE_KEYWORDS):
                pressure_col = orig
                break

    # 4. Поиск столбца температуры
    temperature_col = None
    best_temp_score = -1
    temp_keywords = ["temp", "temperature", "temperatur", "°c", "c", "температура"]
    for orig, norm in zip(cols, normalized_cols):
        score = 0
        for tk in temp_keywords:
            if norm == tk:
                score += 30
            elif norm.startswith(tk):
                score += 20
            elif tk in norm:
                score += 10
        if score > best_temp_score and score > 0:
            best_temp_score = score
            temperature_col = orig

    mapping.time_col = time_col
    mapping.date_col = date_col
    mapping.pressure_col = pressure_col
    mapping.temperature_col = temperature_col
    mapping.unit_col = unit_col

    # Расчёт уверенности
    if (time_col or (date_col and time_col)) and pressure_col:
        mapping.confidence = 0.95
    elif time_col or pressure_col:
        mapping.confidence = 0.5
    else:
        mapping.confidence = 0.0

    return mapping

