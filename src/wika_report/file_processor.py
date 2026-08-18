import logging
import shutil
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from wika_report.analyzer import analyze_data
from wika_report.column_detector import detect_columns
from wika_report.config import AppConfig
from wika_report.csv_reader import read_wika_csv
from wika_report.data_cleaner import clean_and_normalize_data
from wika_report.excel_report import build_excel_report
from wika_report.graph_builder import build_pressure_graph
from wika_report.models import ProcessingResult
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
    """Определяет имя папки для результатов отчёта по Log.No или по имени CSV файла."""
    if custom_meta and hasattr(custom_meta, "log_no") and custom_meta.log_no:
        raw_log = str(custom_meta.log_no).strip()
        if raw_log and raw_log.upper() != "N/A":
            folder_name = raw_log
            for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
                folder_name = folder_name.replace(char, '_')
            folder_name = folder_name.strip(" ._")
            if folder_name:
                return folder_name

    folder_name = fallback_stem
    for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        folder_name = folder_name.replace(char, '_')
    return folder_name.strip(" .") or "report"


def process_single_csv(
    file_path: Path,
    output_dir: Path,
    processed_dir: Path,
    failed_dir: Path,
    config: AppConfig,
    override_custom_meta: Optional[object] = None
) -> ProcessingResult:
    """
    Обрабатывает один файл CSV от начала до конца:
    Чтение -> Поиск столбцов -> Очистка -> Анализ -> График PNG -> Excel XLSX -> TXT отчёт -> Перемещение/копирование.
    Все создаваемые файлы отчёта сохраняются в отдельную папку, названную по Log.No (или по имени файла).
    """
    logger.info(f"==> Начало обработки файла: {file_path.name}")
    warnings: List[str] = []

    res = ProcessingResult(success=False, input_file=file_path)

    try:
        # 1. Чтение CSV
        df_raw, meta = read_wika_csv(file_path, default_unit=config.default_input_unit)
        logger.info(f"[{file_path.name}] Кодировка: {meta.encoding}, Разделитель: '{meta.delimiter}', Заголовок: строка {meta.header_line_idx + 1}")

        # 2. Поиск столбцов
        mapping = detect_columns(df_raw)
        if not mapping.pressure_col or (not mapping.time_col and mapping.time_kind not in ["index"]):
            err_msg = (
                f"Не удалось автоматически определить обязательные столбцы.\n"
                f"Найден столбец времени: '{mapping.time_col}'\n"
                f"Найден столбец давления: '{mapping.pressure_col}'\n"
                f"Доступные столбцы в CSV: {meta.raw_header}"
            )
            raise ValueError(err_msg)

        logger.info(f"[{file_path.name}] Столбец времени: '{mapping.time_col}', Столбец давления: '{mapping.pressure_col}'")

        # 3. Проверка единицы измерения
        if not meta.detected_unit:
            err_msg = (
                f"Не удалось определиться с единицей измерения давления.\n"
                f"В заголовках '{meta.raw_header}' и метаданных {meta.device_info} не найдены названия единиц (bar, psi, kPa, MPa, etc.), "
                f"а параметр 'default_input_unit' в config.json не задан."
            )
            raise ValueError(err_msg)

        logger.info(f"[{file_path.name}] Единица измерения: {meta.detected_unit} (Источник: {meta.detected_unit_source})")

        # 4. Очистка и нормализация данных
        df_clean, stats = clean_and_normalize_data(
            df_raw,
            mapping,
            input_unit=meta.detected_unit,
            decimal_sep=meta.decimal_sep
        )
        logger.info(f"[{file_path.name}] Очистка завершена: {stats.clean_rows} точек принята, {stats.excluded_rows} исключено.")

        # 5. Статистический анализ
        analysis = analyze_data(df_clean, stats, config.analysis)
        
        # Populate custom user metadata from override or config presets
        from wika_report.models import CustomMetadata
        if override_custom_meta:
            analysis.custom_meta = override_custom_meta
            if not getattr(analysis.custom_meta, "pipe_logs_text", None):
                analysis.custom_meta.pipe_logs_text = config.graph.pipe_logs_text
        else:
            analysis.custom_meta = CustomMetadata(
                test_pressure=config.graph.default_test_pressure,
                system=config.graph.default_system,
                log_no=config.graph.default_log_no,
                ins_no=config.graph.default_ins_no,
                custom_date="", # dynamically extracted or filled
                project=config.graph.default_project,
                note=config.graph.default_note,
                wika_nr=config.graph.wika_nr_active,
                pipe_logs_text=config.graph.pipe_logs_text
            )
        
        logger.info(f"[{file_path.name}] Анализ завершён: Мин={analysis.min_pressure_bar:.3f} bar, Макс={analysis.max_pressure_bar:.3f} bar, Длительность={analysis.duration_formatted}")

        # Определяем отдельную папку для лога (по Log.No или по имени файла)
        log_folder_name = get_log_folder_name(analysis.custom_meta, file_path.stem)
        log_output_dir = output_dir / log_folder_name
        log_output_dir.mkdir(parents=True, exist_ok=True)

        # 6. Генерация графика PNG
        graph_file = get_unique_filepath(log_output_dir, file_path.name, ".png")
        build_pressure_graph(
            df=df_clean,
            analysis=analysis,
            graph_cfg=config.graph,
            output_path=graph_file,
            filename_title=file_path.name
        )
        res.graph_path = graph_file
        logger.info(f"[{file_path.name}] График PNG создан: {graph_file.name} в {log_output_dir}")

        # 7. Генерация отчёта Excel XLSX
        excel_file = get_unique_filepath(log_output_dir, file_path.name, ".xlsx")
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
        res.excel_path = excel_file
        logger.info(f"[{file_path.name}] Excel XLSX отчёт создан: {excel_file.name}")

        # 8. Генерация текстового отчёта TXT
        text_file = get_unique_filepath(log_output_dir, file_path.name, ".txt")
        generate_text_report(
            meta=meta,
            mapping=mapping,
            stats=stats,
            analysis=analysis,
            warnings=warnings,
            output_path=text_file
        )
        res.report_path = text_file
        logger.info(f"[{file_path.name}] Текстовый отчёт создан: {text_file.name}")

        # 8.5. Генерация PDF с прикреплёнными фотографиями (если включено)
        if analysis.custom_meta.create_pdf:
            try:
                from wika_report.pdf_report import build_pdf_report
                pdf_file = get_unique_filepath(log_output_dir, file_path.name, ".pdf")
                
                # Copy attached photos to output folder using logo (wika_nr + log_no) prefix or fallback
                copied_photos = []
                wika_num = analysis.custom_meta.wika_nr.strip()
                log_num = analysis.custom_meta.log_no.strip()
                
                parts = []
                if wika_num and wika_num != "N/A":
                    parts.append(wika_num)
                if log_num and log_num != "N/A":
                    parts.append(f"Log_{log_num}")
                
                logo_prefix = "_".join(parts) if parts else file_path.stem
                
                for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ']:
                    logo_prefix = logo_prefix.replace(char, '_')
                
                photo_out_dir = log_output_dir / "attached_photos"
                photo_out_dir.mkdir(parents=True, exist_ok=True)
                
                for idx, p_str in enumerate(analysis.custom_meta.attach_photos, 1):
                    p_path = Path(p_str)
                    if p_path.exists():
                        dest_photo = get_unique_filepath(photo_out_dir, f"{logo_prefix}_photo_{idx}", p_path.suffix)
                        shutil.copy2(str(p_path), str(dest_photo))
                        copied_photos.append(dest_photo)
                        
                build_pdf_report(
                    graph_png_path=graph_file,
                    photo_paths=copied_photos,
                    output_pdf_path=pdf_file
                )
                logger.info(f"[{file_path.name}] PDF отчёт успешно сгенерирован: {pdf_file.name}")
            except Exception as pdf_ex:
                logger.error(f"Ошибка при создании PDF отчёта: {pdf_ex}")
                warnings.append(f"Не удалось сгенерировать PDF отчёт: {pdf_ex}")

        # 9. Перемещение или копирование исходного CSV в processed
        processed_file = get_unique_filepath(processed_dir, file_path.name, ".csv")
        if config.move_processed_files:
            shutil.move(str(file_path), str(processed_file))
        else:
            shutil.copy2(str(file_path), str(processed_file))
        
        res.processed_csv_path = processed_file
        res.success = True
        logger.info(f"[УСПЕХ] Файл {file_path.name} успешно обработан.")

    except Exception as e:
        tb_str = traceback.format_exc()
        logger.error(f"[ОШИБКА] Сбой при обработке файла {file_path.name}: {e}\n{tb_str}")
        res.success = False
        res.error_message = str(e)

        # Перемещение в failed и запись .error.txt
        failed_dir.mkdir(parents=True, exist_ok=True)
        failed_file = get_unique_filepath(failed_dir, file_path.name, ".csv")
        shutil.move(str(file_path), str(failed_file))
        res.failed_csv_path = failed_file

        error_log_file = failed_file.with_suffix(".error.txt")
        with open(error_log_file, "w", encoding="utf-8") as f:
            f.write(f"ОШИБКА ОБРАБОТКИ ФАЙЛА {file_path.name}\n")
            f.write(f"Дата ошибки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Сообщение: {e}\n\n")
            f.write("ТРАССИРОВКА СТЕКА (TRACEBACK):\n")
            f.write(tb_str)

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
