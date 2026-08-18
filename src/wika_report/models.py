from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class FileMetadata:
    """Метаданные CSV-файла и обнаруженные параметры парсинга."""
    input_path: Path
    encoding: str
    delimiter: str
    decimal_sep: str
    header_line_idx: int
    raw_header: List[str]
    device_info: Dict[str, str] = field(default_factory=dict)
    detected_unit: Optional[str] = None
    detected_unit_source: Optional[str] = None


@dataclass
class ColumnMapping:
    """Результат автоматического определения столбцов."""
    time_col: Optional[str] = None
    date_col: Optional[str] = None
    pressure_col: Optional[str] = None
    temperature_col: Optional[str] = None
    unit_col: Optional[str] = None
    time_kind: str = "datetime"  # "datetime", "separate_date_time", "relative_sec", "relative_min", "index"
    confidence: float = 0.0
    notes: List[str] = field(default_factory=list)


@dataclass
class CleaningStats:
    """Статистика очистки исходных данных."""
    total_raw_rows: int = 0
    clean_rows: int = 0
    excluded_rows: int = 0
    exclusion_reasons: Dict[str, int] = field(default_factory=dict)


@dataclass
class HoldPeriodStats:
    """Результаты анализа участка выдержки под давлением."""
    enabled: bool = False
    hold_start_min: Optional[float] = None
    hold_end_min: Optional[float] = None
    test_pressure_bar: Optional[float] = None
    lower_limit_bar: Optional[float] = None
    upper_limit_bar: Optional[float] = None
    allowed_drop_bar: Optional[float] = None
    
    min_pressure: Optional[float] = None
    max_pressure: Optional[float] = None
    mean_pressure: Optional[float] = None
    drop_bar: Optional[float] = None
    
    status: str = "Не оценивалось"  # "PASS", "FAIL", "Не оценивалось"
    fail_reasons: List[str] = field(default_factory=list)


@dataclass
class CustomMetadata:
    """Дополнительные метаданные от пользователя для оформления отчета."""
    test_pressure: str = ""
    system: str = ""
    log_no: str = ""
    ins_no: str = ""
    custom_date: str = ""
    project: str = ""
    note: str = ""
    wika_nr: str = ""
    create_pdf: bool = False
    attach_photos: List[str] = field(default_factory=list)
    pipe_logs_text: str = ""


@dataclass
class AnalysisResult:
    """Итоговые вычисленные метрики и статистический анализ."""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    duration_formatted: str = "00:00:00"
    
    total_raw_rows: int = 0
    valid_points_count: int = 0
    excluded_rows_count: int = 0
    
    start_pressure_bar: float = 0.0
    end_pressure_bar: float = 0.0
    min_pressure_bar: float = 0.0
    max_pressure_bar: float = 0.0
    mean_pressure_bar: float = 0.0
    median_pressure_bar: float = 0.0
    std_pressure_bar: float = 0.0
    
    total_delta_bar: float = 0.0
    range_bar: float = 0.0
    max_pressure_time_str: str = ""
    max_rise_rate_bar_per_min: float = 0.0
    max_drop_rate_bar_per_min: float = 0.0
    
    hold_stats: Optional[HoldPeriodStats] = None
    custom_meta: CustomMetadata = field(default_factory=CustomMetadata)
    has_temperature: bool = False
    min_temp: Optional[float] = None
    max_temp: Optional[float] = None


@dataclass
class ProcessingResult:
    """Результат обработки одного файла CSV."""
    success: bool
    input_file: Path
    excel_path: Optional[Path] = None
    graph_path: Optional[Path] = None
    report_path: Optional[Path] = None
    processed_csv_path: Optional[Path] = None
    failed_csv_path: Optional[Path] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

