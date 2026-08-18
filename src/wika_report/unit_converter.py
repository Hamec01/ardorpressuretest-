from typing import Dict, Union, Sequence
import pandas as pd
import numpy as np


UNIT_CONVERSION_FACTORS: Dict[str, float] = {
    "bar": 1.0,
    "mbar": 0.001,
    "hpa": 0.001,
    "kpa": 0.01,
    "mpa": 10.0,
    "pa": 0.00001,
    "psi": 0.06894757293168361,
    "kgf/cm²": 0.980665,
    "kgf/cm2": 0.980665,
    "kg/cm2": 0.980665,
}

UNIT_ALIASES: Dict[str, str] = {
    "bar": "bar",
    "mbar": "mbar",
    "hpa": "hpa",
    "kpa": "kpa",
    "mpa": "mpa",
    "pa": "pa",
    "psi": "psi",
    "kgf/cm²": "kgf/cm²",
    "kgf/cm2": "kgf/cm²",
    "kg/cm2": "kgf/cm²",
    "бар": "bar",
    "мбар": "mbar",
    "гпа": "hpa",
    "кпа": "kpa",
    "мпа": "mpa",
    "па": "pa",
    "пси": "psi",
}


def normalize_unit_name(unit_str: str) -> str:
    """Нормализует наименование единицы измерения."""
    clean = unit_str.strip().lower()
    # Удалить скобки, слэши и лишние символы
    clean = clean.replace("(", "").replace(")", "").replace("[", "").replace("]", "")
    if "/" in clean and "cm" not in clean and "kg" not in clean:
        clean = clean.split("/")[-1].strip()
    return UNIT_ALIASES.get(clean, clean)


def is_supported_unit(unit_str: str) -> bool:
    """Проверяет, поддерживается ли единица измерения."""
    norm = normalize_unit_name(unit_str)
    return norm in UNIT_CONVERSION_FACTORS


def get_conversion_factor(from_unit: str) -> float:
    """Возвращает множитель для конвертации из from_unit в bar."""
    norm = normalize_unit_name(from_unit)
    if norm not in UNIT_CONVERSION_FACTORS:
        raise ValueError(
            f"Неизвестная или неподдерживаемая единица измерения давления: '{from_unit}'. "
            f"Поддерживаемые единицы: {', '.join(sorted(set(UNIT_CONVERSION_FACTORS.keys())))}"
        )
    return UNIT_CONVERSION_FACTORS[norm]


def convert_value_to_bar(val: float, from_unit: str) -> float:
    """Преобразует числовое значение давления в bar."""
    factor = get_conversion_factor(from_unit)
    return val * factor


def convert_series_to_bar(series: pd.Series, from_unit: str) -> pd.Series:
    """Преобразует pandas Series со значениями давления в bar."""
    factor = get_conversion_factor(from_unit)
    return series * factor
