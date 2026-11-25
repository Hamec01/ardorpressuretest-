import logging
import shutil
import traceback
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from wika_report.analyzer import analyze_data
from wika_report.column_detector import detect_columns
from wika_report.config import AppConfig, GraphConfig
from wika_report.csv_reader import read_wika_csv
from wika_report.data_cleaner import clean_and_normalize_data
from wika_report.excel_report import build_excel_report
from wika_report.graph_builder import build_pressure_graph
from wika_report.manifest import create_artifact_item, write_manifest
from wika_report.models import (
    ArtifactItem,
    CustomMetadata,
    PhotoAttachment,
    ProcessingResult,
    RevisionBuildResult,
    TestInput,
    normalize_log_no,
)
from wika_report.text_report import generate_text_report

logger = logging.getLogger("wika_report")


def get_unique_filepath(target_dir: Path, base_name: str, extension: str) -> Path:
    """Формирует уникальный путь к файлу в target_dir, чтобы не перезаписать существующие файлы."""
    target_dir.mkdir(parents=True, exist_ok=True)
    clean_base = Path(base_name).stem
    candidate = target_dir / f"{clean_base}{extension}"

    if not candidate.exists():
        return candidate

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = target_dir / f"{clean_base}_{timestamp}{extension}"

    counter = 1
    while candidate.exists():
        candidate = target_dir / f"{clean_base}_{timestamp}_{counter}{extension}"
        counter += 1

    return candidate


def get_log_folder_name(custom_meta: Optional[object], fallback_stem: str) -> str:
    """Определяет нормализованное имя папки для лога по Log.No или по имени CSV-файла."""
    raw_log = None
    if custom_meta and hasattr(custom_meta, "log_no"):
        raw_log = custom_meta.log_no
    return normalize_log_no(raw_log, fallback_name=fallback_stem)


GRAPH_HIDEABLE_HEADER_FIELDS = ("system", "ins_no", "project", "note")


def normalize_hidden_header_fields(values) -> List[str]:
    """Keep only known header fields, in a fixed order; accepts a list or a comma-separated string."""
    if values is None:
        return []
    if isinstance(values, str):
        values = values.split(",")
    wanted = {str(v).strip().lower() for v in values}
    return [name for name in GRAPH_HIDEABLE_HEADER_FIELDS if name in wanted]


def graph_config_for_log(
    config: AppConfig,
    plot_temperature: Optional[bool] = None,
    hidden_header_fields: Optional[List[str]] = None,
    start_from_zero: bool | None = None,
    zero_ramp_seconds: float | None = None,
) -> GraphConfig:
    """Graph settings with the per-log choices applied (None keeps the config value)."""
    changes = {}
    if plot_temperature is not None:
        changes["plot_temperature"] = bool(plot_temperature)
    if hidden_header_fields is not None:
        changes["hidden_header_fields"] = normalize_hidden_header_fields(hidden_header_fields)
    if start_from_zero is not None:
        changes["start_from_zero"] = bool(start_from_zero)
    if zero_ramp_seconds is not None:
        changes["zero_ramp_seconds"] = float(zero_ramp_seconds)
    return replace(config.graph, **changes) if changes else config.graph


def metadata_hidden_header_fields(metadata: dict) -> Optional[List[str]]:
    """Stored header fields hidden on the graph of a log; None for logs made before the choice existed."""
    value = (metadata or {}).get("graph_hidden_fields")
    return None if value is None else normalize_hidden_header_fields(value)


def metadata_optional_bool(metadata: dict, key: str) -> bool | None:
    """Read an optional stored boolean, including legacy string values."""
    value = (metadata or {}).get(key)
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def metadata_plot_temperature(metadata: dict) -> Optional[bool]:
    """Read the stored temperature choice; None preserves the config for old logs."""
    return metadata_optional_bool(metadata, "plot_temperature")


def render_graph_png(
    csv_path: Path,
    metadata: dict,
    output_path: Path,
    config: Optional[AppConfig] = None,
) -> Path:
    """Draw only the pressure graph of ``csv_path`` with the given header values.

    Used by the PTR: the protocol prints its own copy of the graph with the protocol
    values, the log's stored files are not touched. Empty values are printed as N/A.
    """
    config = config or AppConfig()
    df_raw, meta = read_wika_csv(csv_path, default_unit=config.default_input_unit)
    mapping = detect_columns(df_raw)
    if not mapping.pressure_col or not meta.detected_unit:
        raise ValueError("Pressure column or unit not found in the CSV.")
    df_clean, stats = clean_and_normalize_data(df_raw, mapping, input_unit=meta.detected_unit, decimal_sep=meta.decimal_sep)
    analysis = analyze_data(df_clean, stats, config.analysis)

    def text(key: str) -> str:
        return str(metadata.get(key) or "").strip()

    analysis.custom_meta = CustomMetadata(
        test_pressure=text("test_pressure"),
        system=text("system"),
        log_no=text("log_no"),
        ins_no=text("ins_no"),
        custom_date=text("custom_date"),
        project=text("project"),
        note=text("note"),
        wika_nr=text("wika_nr"),
        operator=text("operator"),
        pipe_logs_text=text("pipe_logs_text"),
    )
    build_pressure_graph(
        df=df_clean,
        analysis=analysis,
        graph_cfg=graph_config_for_log(
            config,
            plot_temperature=metadata_plot_temperature(metadata),
            hidden_header_fields=metadata_hidden_header_fields(metadata),
            start_from_zero=metadata_optional_bool(metadata, "graph_start_from_zero"),
            zero_ramp_seconds=metadata.get("graph_zero_ramp_seconds"),
        ),
        output_path=output_path,
        filename_title=csv_path.name,
    )
    return output_path


def process_test_input(
    test_input: TestInput,
    output_base_dir: Path,
    config: AppConfig
) -> RevisionBuildResult:
    """
    Каноническая точка входа ядра обработки давления:
    1. Нормализует Log No.
    2. Создаёт изолированную папку лога / ревизии.
    3. Выполняет парсинг CSV, поиск столбцов, очистку и статистический анализ.
    4. Генерирует артефакты: PNG-график, Excel XLSX, текстовый отчёт TXT, PDF (опционально).
    5. Копирует исходный CSV и прикреплённые фотографии в ревизионный каталог.
    6. Рассчитывает SHA-256 для каждого файла и создаёт атомарный manifest.json.
    7. При повторной обработке архивирует предыдущую ревизию (No-overwrite policy).
    """
    csv_file = test_input.csv_path
    normalized_log = normalize_log_no(test_input.log_no, fallback_name=csv_file.stem)
    revision_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    warnings: List[str] = []

    log_dir = output_base_dir / normalized_log
    log_dir.mkdir(parents=True, exist_ok=True)

    result = RevisionBuildResult(
        success=False,
        log_no=normalized_log,
        revision_id=revision_id,
        revision_dir=log_dir
    )

    try:
        # Если в папке уже есть манифест предыдущего запуска, сохраняем его в историю ревизий
        existing_manifest = log_dir / "manifest.json"
        if existing_manifest.exists():
            history_dir = log_dir / "revisions" / f"rev_{revision_id}"
            history_dir.mkdir(parents=True, exist_ok=True)
            # Архивируем предыдущий манифест в историю
            shutil.copy2(str(existing_manifest), str(history_dir / "manifest.json"))
            logger.info(f"Preserved previous revision manifest to {history_dir}")

        # 1. Чтение CSV
        df_raw, meta = read_wika_csv(csv_file, default_unit=config.default_input_unit)
        logger.info(f"[{csv_file.name}] Кодировка: {meta.encoding}, Разделитель: '{meta.delimiter}', Заголовок: строка {meta.header_line_idx + 1}")

        # 2. Определение столбцов
        mapping = detect_columns(df_raw)
        if not mapping.pressure_col or (not mapping.time_col and mapping.time_kind not in ["index"]):
            err_msg = (
                f"Не удалось автоматически определить обязательные столбцы.\n"
                f"Найден столбец времени: '{mapping.time_col}'\n"
                f"Найден столбец давления: '{mapping.pressure_col}'\n"
                f"Доступные столбцы в CSV: {meta.raw_header}"
            )
            raise ValueError(err_msg)

        # 3. Единица измерения
        if not meta.detected_unit:
            err_msg = (
                f"Не удалось определиться с единицей измерения давления.\n"
                f"В заголовках '{meta.raw_header}' и метаданных {meta.device_info} не найдены названия единиц (bar, psi, kPa, MPa), "
                f"а параметр 'default_input_unit' в config.json не задан."
            )
            raise ValueError(err_msg)

        # 4. Очистка данных
        df_clean, stats = clean_and_normalize_data(
            df_raw,
            mapping,
            input_unit=meta.detected_unit,
            decimal_sep=meta.decimal_sep
        )

        # 5. Статистический анализ
        analysis = analyze_data(df_clean, stats, config.analysis)

        # Заполнение метаданных анализа.
        # Пустое поле остаётся пустым (на графике будет N/A). Примерные значения
        # config.graph.default_* (64700, NB1402PM-13388, 24bar, ...) — это только
        # стартовые значения полей desktop-GUI; молча подставлять их в документы нельзя.
        pipe_logs_text = "\n".join(test_input.pipe_numbers) if test_input.pipe_numbers else ""
        analysis.custom_meta = CustomMetadata(
            test_pressure=(test_input.test_pressure or "").strip(),
            system=(test_input.system or "").strip(),
            log_no=normalized_log,
            ins_no=(test_input.ins_no or "").strip(),
            custom_date=test_input.custom_date,
            project=(test_input.project or "").strip(),
            note=(test_input.note or "").strip(),
            wika_nr=(test_input.wika_nr or "").strip(),
            operator=test_input.operator,
            bundle_numbers=test_input.bundle_numbers,
            pipe_numbers=test_input.pipe_numbers,
            create_pdf=test_input.create_pdf,
            pipe_logs_text=pipe_logs_text or config.graph.pipe_logs_text
        )

        artifacts: List[ArtifactItem] = []

        # 6. Копирование исходного CSV в revision source/
        source_dir = log_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        dest_csv = source_dir / csv_file.name
        shutil.copy2(str(csv_file), str(dest_csv))
        result.source_csv_path = dest_csv
        artifacts.append(create_artifact_item(dest_csv, log_dir, file_type="source_csv"))

        # 7. Генерация графика PNG
        graph_file = log_dir / f"{csv_file.stem}.png"
        graph_cfg = graph_config_for_log(
            config,
            plot_temperature=test_input.plot_temperature,
            hidden_header_fields=test_input.graph_hidden_fields,
            start_from_zero=test_input.graph_start_from_zero,
            zero_ramp_seconds=test_input.graph_zero_ramp_seconds,
        )
        build_pressure_graph(
            df=df_clean,
            analysis=analysis,
            graph_cfg=graph_cfg,
            output_path=graph_file,
            filename_title=csv_file.name
        )
        result.graph_path = graph_file
        artifacts.append(create_artifact_item(graph_file, log_dir, file_type="graph_png"))

        # 8. Генерация отчёта Excel XLSX
        excel_file = log_dir / f"{csv_file.stem}.xlsx"
        build_excel_report(
            df_raw=df_raw,
            df_clean=df_clean,
            meta=meta,
            mapping=mapping,
            stats=stats,
            analysis=analysis,
            graph_path=graph_file,
            output_path=excel_file
        )
        result.excel_path = excel_file
        artifacts.append(create_artifact_item(excel_file, log_dir, file_type="excel_xlsx"))

        # 9. Генерация текстового отчёта TXT
        text_file = log_dir / f"{csv_file.stem}.txt"
        generate_text_report(
            meta=meta,
            mapping=mapping,
            stats=stats,
            analysis=analysis,
            warnings=warnings,
            output_path=text_file
        )
        result.report_path = text_file
        artifacts.append(create_artifact_item(text_file, log_dir, file_type="text_txt"))

        # 10. Фотографии и PDF-отчёт
        copied_photos: List[Path] = []
        if test_input.photos or analysis.custom_meta.create_pdf:
            photo_out_dir = log_dir / "attached_photos"
            photo_out_dir.mkdir(parents=True, exist_ok=True)

            wika_clean = analysis.custom_meta.wika_nr.strip()
            log_clean = normalized_log
            parts = []
            if wika_clean and wika_clean.upper() != "N/A":
                parts.append(wika_clean)
            if log_clean and log_clean.upper() != "N/A":
                parts.append(f"Log_{log_clean}")
            logo_prefix = "_".join(parts) if parts else csv_file.stem
            for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ']:
                logo_prefix = logo_prefix.replace(char, '_')

            for idx, photo_obj in enumerate(test_input.photos, 1):
                p_path = photo_obj.path if isinstance(photo_obj, PhotoAttachment) else Path(str(photo_obj))
                cat = photo_obj.category if isinstance(photo_obj, PhotoAttachment) else "other"
                if p_path.exists():
                    dest_photo = get_unique_filepath(photo_out_dir, f"{logo_prefix}_photo_{idx}", p_path.suffix)
                    shutil.copy2(str(p_path), str(dest_photo))
                    copied_photos.append(dest_photo)
                    artifacts.append(create_artifact_item(dest_photo, log_dir, file_type="photo", category=cat))

            if test_input.create_pdf:
                try:
                    from wika_report.pdf_report import build_pdf_report
                    pdf_file = log_dir / f"{csv_file.stem}.pdf"
                    build_pdf_report(
                        graph_png_path=graph_file,
                        photo_paths=copied_photos,
                        output_pdf_path=pdf_file
                    )
                    result.pdf_path = pdf_file
                    artifacts.append(create_artifact_item(pdf_file, log_dir, file_type="report_pdf"))
                    logger.info(f"[{csv_file.name}] PDF отчёт успешно создан: {pdf_file.name}")
                except Exception as pdf_ex:
                    logger.error(f"Ошибка при создании PDF отчёта: {pdf_ex}")
                    warnings.append(f"Не удалось создать PDF отчёт: {pdf_ex}")

        # 11. Создание манифеста ревизии manifest.json
        manifest_file = log_dir / "manifest.json"
        manifest_meta = {
            "test_pressure": analysis.custom_meta.test_pressure,
            "system": analysis.custom_meta.system,
            "log_no": normalized_log,
            "ins_no": analysis.custom_meta.ins_no,
            "custom_date": analysis.custom_meta.custom_date,
            "project": analysis.custom_meta.project,
            "note": analysis.custom_meta.note,
            "wika_nr": analysis.custom_meta.wika_nr,
            "operator": analysis.custom_meta.operator,
            "bundle_numbers": analysis.custom_meta.bundle_numbers,
            "pipe_numbers": analysis.custom_meta.pipe_numbers,
            "plot_temperature": bool(graph_cfg.plot_temperature),
            "graph_hidden_fields": list(graph_cfg.hidden_header_fields or []),
            "graph_start_from_zero": graph_cfg.start_from_zero,
            "graph_zero_ramp_seconds": graph_cfg.zero_ramp_seconds,
        }
        manifest_metrics = {
            "start_time": analysis.start_time.isoformat() if analysis.start_time else None,
            "end_time": analysis.end_time.isoformat() if analysis.end_time else None,
            "duration_formatted": analysis.duration_formatted,
            "min_pressure_bar": analysis.min_pressure_bar,
            "max_pressure_bar": analysis.max_pressure_bar,
            "mean_pressure_bar": analysis.mean_pressure_bar,
            "total_delta_bar": analysis.total_delta_bar,
            "evaluation_status": analysis.hold_stats.status if analysis.hold_stats else "Не оценивалось",
        }

        write_manifest(
            manifest_path=manifest_file,
            log_no=normalized_log,
            revision_id=revision_id,
            metadata=manifest_meta,
            metrics=manifest_metrics,
            artifacts=artifacts,
            created_by=test_input.operator or "operator"
        )
        result.manifest_path = manifest_file
        result.warnings = warnings
        result.success = True

        # 12. Создание mutable workflow sidecar pipecloud_status.txt (не входит в hash-манифест)
        pipecloud_status_file = log_dir / "pipecloud_status.txt"
        if not pipecloud_status_file.exists():
            try:
                with open(pipecloud_status_file, "w", encoding="utf-8") as pcs:
                    pcs.write(
                        f"PIPECLOUD WORKFLOW STATUS\n"
                        f"Log No.: {normalized_log}\n"
                        f"Added to PipeCloud: No\n"
                        f"Updated by: System\n"
                        f"Updated at: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                    )
            except Exception as pc_ex:
                logger.warning(f"Could not create pipecloud_status.txt: {pc_ex}")
        
        # Автоматическое добавление в локальную очередь синхронизации
        try:
            from wika_report.sync_queue import sync_queue
            sync_queue.enqueue_revision(normalized_log, revision_id, manifest_file)
        except Exception as q_ex:
            logger.warning(f"Failed to enqueue to sync queue: {q_ex}")

        logger.info(f"[УСПЕХ] Ревизия лога {normalized_log} (ID: {revision_id}) успешно сформирована.")

    except Exception as e:
        tb_str = traceback.format_exc()
        logger.error(f"[ОШИБКА] Сбой при обработке испытания {csv_file.name}: {e}\n{tb_str}")
        result.success = False
        result.error_message = str(e)
        result.warnings = warnings

    return result


def process_single_csv(
    file_path: Path,
    output_dir: Path,
    processed_dir: Path,
    failed_dir: Path,
    config: AppConfig,
    override_custom_meta: Optional[object] = None
) -> ProcessingResult:
    """
    Обрабатывает один CSV-файл и сохраняет ретро-совместимый интерфейс:
    - Конвертирует параметры в TestInput;
    - Вызывает каноническое ядро process_test_input;
    - Обеспечивает перемещение/копирование в processed/failed.
    """
    logger.info(f"==> Начало обработки файла: {file_path.name}")
    res = ProcessingResult(success=False, input_file=file_path)

    # Подготавливаем TestInput
    photos = []
    log_no_val = ""
    test_press_val = ""
    sys_val = ""
    ins_val = ""
    proj_val = ""
    note_val = ""
    wika_val = ""
    op_val = ""
    create_pdf_val = False
    bundles = []
    pipes = []

    if override_custom_meta:
        log_no_val = getattr(override_custom_meta, "log_no", "")
        test_press_val = getattr(override_custom_meta, "test_pressure", "")
        sys_val = getattr(override_custom_meta, "system", "")
        ins_val = getattr(override_custom_meta, "ins_no", "")
        proj_val = getattr(override_custom_meta, "project", "")
        note_val = getattr(override_custom_meta, "note", "")
        wika_val = getattr(override_custom_meta, "wika_nr", "")
        op_val = getattr(override_custom_meta, "operator", "")
        create_pdf_val = getattr(override_custom_meta, "create_pdf", False)
        bundles = getattr(override_custom_meta, "bundle_numbers", [])
        
        # Получение списка труб
        pipe_text = getattr(override_custom_meta, "pipe_logs_text", "")
        if pipe_text:
            pipes = [p.strip() for p in pipe_text.splitlines() if p.strip()]
        else:
            pipes = getattr(override_custom_meta, "pipe_numbers", [])
            
        for photo_item in getattr(override_custom_meta, "attach_photos", []):
            if isinstance(photo_item, PhotoAttachment):
                photos.append(photo_item)
            elif isinstance(photo_item, (str, Path)):
                photos.append(PhotoAttachment(path=Path(photo_item), category="other"))
    else:
        log_no_val = config.graph.default_log_no
        test_press_val = config.graph.default_test_pressure
        sys_val = config.graph.default_system
        ins_val = config.graph.default_ins_no
        proj_val = config.graph.default_project
        note_val = config.graph.default_note
        wika_val = config.graph.wika_nr_active
        if config.graph.pipe_logs_text:
            pipes = [p.strip() for p in config.graph.pipe_logs_text.splitlines() if p.strip()]

    test_input = TestInput(
        csv_path=file_path,
        log_no=log_no_val,
        test_pressure=test_press_val,
        system=sys_val,
        ins_no=ins_val,
        project=proj_val,
        note=note_val,
        wika_nr=wika_val,
        operator=op_val,
        bundle_numbers=bundles,
        pipe_numbers=pipes,
        create_pdf=create_pdf_val,
        photos=photos
    )

    core_result = process_test_input(test_input, output_base_dir=output_dir, config=config)

    res.success = core_result.success
    res.graph_path = core_result.graph_path
    res.excel_path = core_result.excel_path
    res.report_path = core_result.report_path
    res.revision_dir = core_result.revision_dir
    res.manifest_path = core_result.manifest_path
    res.error_message = core_result.error_message
    res.warnings = core_result.warnings

    if core_result.success:
        processed_dir.mkdir(parents=True, exist_ok=True)
        processed_file = get_unique_filepath(processed_dir, file_path.name, ".csv")
        if config.move_processed_files:
            shutil.move(str(file_path), str(processed_file))
        else:
            shutil.copy2(str(file_path), str(processed_file))
        res.processed_csv_path = processed_file
    else:
        failed_dir.mkdir(parents=True, exist_ok=True)
        failed_file = get_unique_filepath(failed_dir, file_path.name, ".csv")
        shutil.move(str(file_path), str(failed_file))
        res.failed_csv_path = failed_file

        error_log_file = failed_file.with_suffix(".error.txt")
        with open(error_log_file, "w", encoding="utf-8") as f:
            f.write(f"ОШИБКА ОБРАБОТКИ ФАЙЛА {file_path.name}\n")
            f.write(f"Дата ошибки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Сообщение: {core_result.error_message}\n")

    return res


def process_batch(
    input_dir: Path,
    output_dir: Path,
    processed_dir: Path,
    failed_dir: Path,
    config: AppConfig,
    specific_file: Optional[Path] = None
) -> List[ProcessingResult]:
    """
    Пакетная обработка всех CSV-файлов в папке input или одного выбранного файла.
    """
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    if specific_file:
        files = [specific_file]
    else:
        files = [
            f for f in input_dir.glob("*.csv")
            if f.is_file() and not f.name.startswith("~") and not f.name.startswith(".")
        ]

    results = []
    for f in files:
        res = process_single_csv(
            file_path=f,
            output_dir=output_dir,
            processed_dir=processed_dir,
            failed_dir=failed_dir,
            config=config
        )
        results.append(res)

    return results
