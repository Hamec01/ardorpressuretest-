import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import charset_normalizer
import pandas as pd

from wika_report.models import FileMetadata
from wika_report.unit_converter import is_supported_unit, normalize_unit_name


ENCODING_CANDIDATES = [
    "utf-8-sig",
    "utf-8",
    "windows-1251",
    "windows-1252",
    "latin-1",
]

DELIMITERS = [";", ",", "\t"]


def detect_encoding(file_path: Path) -> str:
    """Определяет кодировку файла с помощью charset_normalizer или перебора."""
    try:
        with open(file_path, "rb") as f:
            raw_bytes = f.read(32768)
        
        matches = charset_normalizer.from_bytes(raw_bytes)
        best = matches.best()
        if best and best.encoding:
            enc = best.encoding.lower()
            if enc in ["utf-8", "utf-8-sig", "utf8"]:
                return "utf-8-sig" if raw_bytes.startswith(b"\xef\xbb\xbf") else "utf-8"
            return enc
    except Exception:
        pass

    # Перебор кандидатов
    for enc in ENCODING_CANDIDATES:
        try:
            with open(file_path, "r", encoding=enc) as f:
                f.read(4096)
            return enc
        except (UnicodeDecodeError, Exception):
            continue

    return "utf-8"


def read_file_lines(file_path: Path, encoding: str, max_lines: int = 100) -> List[str]:
    """Считывает первые max_lines строк файла."""
    lines = []
    with open(file_path, "r", encoding=encoding, errors="replace") as f:
        for _ in range(max_lines):
            line = f.readline()
            if not line:
                break
            lines.append(line.strip("\r\n"))
    return lines


def detect_delimiter_and_header(lines: List[str]) -> Tuple[str, int, str]:
    """
    Анализирует строки и находит:
    1. Наиболее вероятный разделитель (';', ',', '\t').
    2. Индекс строки заголовка таблицы.
    3. Наиболее вероятный десятичный разделитель (',', '.').
    """
    time_keywords = ["time", "timestamp", "date", "zeit", "datum", "aika", "время", "дата"]
    pressure_keywords = ["pressure", "druck", "paine", "bar", "psi", "kpa", "mpa", "давление", "messwert"]

    best_header_idx = 0
    best_delimiter = ";"
    max_score = -1

    for idx, line in enumerate(lines[:30]):
        line_lower = line.lower()
        if not line_lower.strip():
            continue

        for delim in DELIMITERS:
            parts = [p.strip() for p in line.split(delim) if p.strip()]
            if len(parts) < 2:
                continue

            score = 0
            # Проверка ключевых слов
            for part in parts:
                p_low = part.lower()
                if any(tk in p_low for tk in time_keywords):
                    score += 5
                if any(pk in p_low for pk in pressure_keywords):
                    score += 5
                if is_supported_unit(p_low):
                    score += 3

            # Дополнительные очки за разделитель
            if delim == ";":
                score += 1

            if score > max_score:
                max_score = score
                best_header_idx = idx
                best_delimiter = delim

    # Определяем десятичный знак по первому блоку данных под заголовком
    decimal_sep = ","
    if best_header_idx + 1 < len(lines):
        sample_data_lines = lines[best_header_idx + 1: best_header_idx + 10]
        dot_count = 0
        comma_count = 0
        for dline in sample_data_lines:
            parts = dline.split(best_delimiter)
            for p in parts:
                p_clean = p.strip()
                if re.match(r"^\d+\,\d+$", p_clean):
                    comma_count += 1
                elif re.match(r"^\d+\.\d+$", p_clean):
                    dot_count += 1
        if dot_count > comma_count:
            decimal_sep = "."

    return best_delimiter, best_header_idx, decimal_sep


def extract_device_info(pre_header_lines: List[str]) -> Dict[str, str]:
    """Извлекает служебные данные прибора WIKA CPG1500 из строк перед заголовком."""
    device_info = {}
    for line in pre_header_lines:
        line_clean = line.strip("#; \t")
        if not line_clean:
            continue
        if ":" in line_clean:
            k, v = line_clean.split(":", 1)
            device_info[k.strip()] = v.strip()
        elif "=" in line_clean:
            k, v = line_clean.split("=", 1)
            device_info[k.strip()] = v.strip()
        elif ";" in line_clean:
            parts = [p.strip() for p in line_clean.split(";") if p.strip()]
            if len(parts) == 2:
                device_info[parts[0]] = parts[1]
    return device_info


def extract_unit_from_header_or_metadata(header_cols: List[str], device_info: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    """Ищет явное указание единиц измерения давления в заголовках колонок или служебных строках."""
    # 1. Заголовки столбцов (например, "Pressure / bar", "Druck (psi)", "Pressure [kPa]")
    for col in header_cols:
        col_clean = col.strip()
        # Поиск по шаблону "/ unit" или "(unit)" или "[unit]"
        match = re.search(r"[\/\(\[\s]+([a-zA-Z°²0-9]+)[\)\]\s]*$", col_clean)
        if match:
            potential_unit = match.group(1).strip()
            if is_supported_unit(potential_unit):
                return normalize_unit_name(potential_unit), f"Заголовок столбца '{col}'"

    # 2. Метаданные прибора
    for key, val in device_info.items():
        if any(w in key.lower() for w in ["unit", "единица", "einheit"]):
            if is_supported_unit(val):
                return normalize_unit_name(val), f"Служебные данные ({key})"

    return None, None


def read_wika_csv(file_path: Path, default_unit: Optional[str] = None) -> Tuple[pd.DataFrame, FileMetadata]:
    """
    Полное чтение CSV-файла WIKA CPG1500.
    Автоматически определяет кодировку, разделитель, десятичный знак, метаданные и заголовок.
    """
    encoding = detect_encoding(file_path)
    lines = read_file_lines(file_path, encoding, max_lines=50)

    if not lines:
        raise ValueError(f"Файл {file_path.name} пуст.")

    delimiter, header_idx, decimal_sep = detect_delimiter_and_header(lines)

    pre_header = lines[:header_idx]
    device_info = extract_device_info(pre_header)

    # Чтение данных с помощью pandas
    try:
        df = pd.read_csv(
            file_path,
            encoding=encoding,
            sep=delimiter,
            skiprows=header_idx,
            dtype=str,
            on_bad_lines="skip",
            engine="python"
        )
    except Exception as e:
        raise ValueError(f"Не удалось прочитать CSV-файл {file_path.name}: {e}")

    # Очистка имен столбцов от сносок и трейлинг пустых столбцов
    df.columns = [str(c).strip() for c in df.columns]
    # Удалить полностью пустые или unnamed столбцы без данных
    unnamed_cols = [c for c in df.columns if not c or c.startswith("Unnamed:")]
    for uc in unnamed_cols:
        if df[uc].isna().all() or (df[uc].str.strip() == "").all():
            df.drop(columns=[uc], inplace=True)

    header_cols = list(df.columns)
    unit, unit_source = extract_unit_from_header_or_metadata(header_cols, device_info)

    if not unit and default_unit and is_supported_unit(default_unit):
        unit = normalize_unit_name(default_unit)
        unit_source = "Значение default_input_unit из config.json"

    meta = FileMetadata(
        input_path=file_path,
        encoding=encoding,
        delimiter=delimiter,
        decimal_sep=decimal_sep,
        header_line_idx=header_idx,
        raw_header=header_cols,
        device_info=device_info,
        detected_unit=unit,
        detected_unit_source=unit_source
    )

    return df, meta
