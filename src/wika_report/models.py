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
    operator: str = ""
    bundle_numbers: List[str] = field(default_factory=list)
    pipe_numbers: List[str] = field(default_factory=list)
    create_pdf: bool = False
    attach_photos: List[str] = field(default_factory=list)
    pipe_logs_text: str = ""


@dataclass
class PhotoAttachment:
    """Прикреплённая фотография с категорией."""
    path: Path
    category: str = "other"  # "pipe", "gauge", "installation", "other"


@dataclass
class TestInput:
    """Канонический DTO входных данных для обработки испытания."""
    __test__ = False
    csv_path: Path
    log_no: str = ""
    test_pressure: str = ""
    system: str = ""
    ins_no: str = ""
    custom_date: str = ""
    project: str = ""
    note: str = ""
    wika_nr: str = ""
    operator: str = ""
    bundle_numbers: List[str] = field(default_factory=list)
    pipe_numbers: List[str] = field(default_factory=list)
    create_pdf: bool = False
    photos: List[PhotoAttachment] = field(default_factory=list)


@dataclass
class ArtifactItem:
    """Описание одного артефакта в манифесте ревизии."""
    name: str
    relative_path: str
    file_type: str  # "source_csv", "graph_png", "excel_xlsx", "text_txt", "report_pdf", "photo", "manifest"
    size_bytes: int
    sha256: str
    category: Optional[str] = None


@dataclass
class RevisionManifest:
    """Неизменяемый манифест ревизии с метаданными и контрольными суммами."""
    manifest_version: str = "1.0"
    core_version: str = "1.0.0"
    log_no: str = ""
    revision_id: str = ""
    created_at_utc: str = ""
    created_by: str = "operator"
    metadata: Dict[str, object] = field(default_factory=dict)
    metrics: Dict[str, object] = field(default_factory=dict)
    artifacts: List[ArtifactItem] = field(default_factory=list)


@dataclass
class RevisionBuildResult:
    """Полный результат сборки атомарной ревизии."""
    success: bool
    log_no: str
    revision_id: str
    revision_dir: Path
    manifest_path: Optional[Path] = None
    graph_path: Optional[Path] = None
    excel_path: Optional[Path] = None
    report_path: Optional[Path] = None
    pdf_path: Optional[Path] = None
    source_csv_path: Optional[Path] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


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
    """Результат обработки одного файла CSV (для обратной совместимости)."""
    success: bool
    input_file: Path
    excel_path: Optional[Path] = None
    graph_path: Optional[Path] = None
    report_path: Optional[Path] = None
    processed_csv_path: Optional[Path] = None
    failed_csv_path: Optional[Path] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    revision_dir: Optional[Path] = None
    manifest_path: Optional[Path] = None


def normalize_log_no(raw_log: Optional[str], fallback_name: str = "report") -> str:
    """
    Нормализует Log No.:
    - удаляет начальные/конечные пробелы;
    - убирает префикс 'Log_' (presentation prefix), если пользователь или генератор его добавил;
    - заменяет символы, недопустимые в файловых путях Windows.
    """
    if not raw_log:
        val = fallback_name
    else:
        val = str(raw_log).strip()
        if not val or val.upper() == "N/A":
            val = fallback_name
        else:
            if val.startswith("Log_") or val.startswith("log_") or val.startswith("LOG_"):
                val = val[4:].strip()
            if not val:
                val = fallback_name

    for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        val = val.replace(ch, '_')
    val = val.strip(" ._")
    return val or "report"


