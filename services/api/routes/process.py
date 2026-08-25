import hashlib
import io
import json
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload
from services.api.database import get_db
from services.api.models import Artifact, Bundle, Pipe, PressureTest, TestRevision
from services.api.schemas import PressureTestResponse
from services.api.storage import storage
from wika_report.config import AppConfig
from wika_report.file_processor import process_test_input
from wika_report.models import PhotoAttachment, TestInput, normalize_log_no

logger = logging.getLogger("ardor_api")
router = APIRouter(prefix="/api/v1/process", tags=["Processing"])


def purge_archived_test_revisions(test: PressureTest, db: Session) -> None:
    revisions = db.query(TestRevision).filter(TestRevision.pressure_test_id == test.id).all()
    for revision in revisions:
        for artifact in revision.artifacts:
            file_path = storage.get_file_path(artifact.storage_key)
            if file_path and file_path.exists():
                file_path.unlink()
        db.delete(revision)


async def _save_photo_artifacts(
    db: Session,
    rev: TestRevision,
    norm_log: str,
    revision_id: str,
    files: List[UploadFile],
    category: str,
) -> None:
    """Сохраняет фотографии как артефакты ревизии напрямую, без конвейера обработки CSV (используется черновиками)."""
    for pf in files:
        if not pf.filename:
            continue
        content = await pf.read()
        if not content:
            continue
        rel_p = f"attached_photos/{pf.filename}"
        storage_key = f"logs/{norm_log}/revisions/{revision_id}/{rel_p}"
        storage.store_file(storage_key, io.BytesIO(content))
        db.add(Artifact(
            test_revision_id=rev.id,
            name=pf.filename,
            relative_path=rel_p,
            file_type="photo",
            category=category,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            storage_key=storage_key
        ))


async def _create_draft_revision(
    db: Session,
    norm_log: str,
    test_pressure: str,
    system: str,
    ins_no: str,
    project: str,
    note: str,
    wika_nr: str,
    operator: str,
    pipe_numbers: List[str],
    bundle_numbers: List[str],
    pipe_photos: List[UploadFile],
    gauge_photos: List[UploadFile],
    other_photos: List[UploadFile],
) -> PressureTest:
    """
    Создаёт черновик испытания (Log No. + метаданные) без CSV-файла измерений.
    Ревизия получает status="draft", пустые metrics_json (замеры ещё не загружены)
    и не проходит через конвейер обработки WIKA CPG1500. CSV можно будет загрузить позже —
    повторная отправка формы с тем же Log No. и файлом создаст полноценную ревизию поверх черновика.
    """
    test = db.query(PressureTest).filter(PressureTest.log_no == norm_log).first()
    if not test:
        test = PressureTest(log_no=norm_log)
        db.add(test)
        db.flush()
    elif test.is_archived:
        purge_archived_test_revisions(test, db)
        test.is_archived = False

    revision_id = f"draft_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    db.query(TestRevision).filter(TestRevision.pressure_test_id == test.id).update({"is_primary": False})

    rev = TestRevision(
        pressure_test_id=test.id,
        revision_id=revision_id,
        status="draft",
        is_primary=True,
        operator=operator or "operator",
        metadata_json={
            "test_pressure": test_pressure,
            "system": system,
            "ins_no": ins_no,
            "project": project,
            "note": note,
            "wika_nr": wika_nr,
            "pipe_numbers": pipe_numbers,
            "bundle_numbers": bundle_numbers,
        },
        metrics_json={}
    )
    db.add(rev)
    db.flush()

    await _save_photo_artifacts(db, rev, norm_log, revision_id, pipe_photos, "pipe")
    await _save_photo_artifacts(db, rev, norm_log, revision_id, gauge_photos, "gauge")
    await _save_photo_artifacts(db, rev, norm_log, revision_id, other_photos, "other")

    for p in pipe_numbers:
        db.add(Pipe(test_revision_id=rev.id, pipe_number=p))
    for b in bundle_numbers:
        db.add(Bundle(test_revision_id=rev.id, bundle_number=b))

    db.commit()

    return (
        db.query(PressureTest)
        .options(joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts))
        .filter(PressureTest.id == test.id)
        .first()
    )


@router.post("", response_model=PressureTestResponse)
async def process_csv_web(
    csv_file: Optional[UploadFile] = File(None, description="CSV-файл манометра WIKA CPG1500 (необязателен для черновика)"),
    log_no: str = Form(..., description="Log No. (например 014FED)"),
    test_pressure: str = Form("", description="Испытательное давление"),
    system: str = Form("", description="Система трубопровода"),
    ins_no: str = Form("", description="Inspection Number"),
    project: str = Form("", description="Проект"),
    note: str = Form("", description="Примечания"),
    wika_nr: str = Form("", description="Номер манометра"),
    operator: str = Form("", description="Оператор"),
    pipe_numbers_raw: str = Form("", description="Список номеров труб"),
    bundle_numbers_raw: str = Form("", description="Список номеров бандлов"),
    create_pdf: bool = Form(True, description="Создавать PDF-отчёт"),
    pipe_photos: List[UploadFile] = File([], description="Фотографии труб"),
    gauge_photos: List[UploadFile] = File([], description="Фотографии манометра"),
    other_photos: List[UploadFile] = File([], description="Прочие фотографии"),
    db: Session = Depends(get_db)
):
    """
    Веб-обработка CSV через единое каноническое ядро WIKA CPG1500:
    1. Принимает CSV и прикреплённые фото;
    2. Прогоняет полный конвейер (read -> detect -> clean -> analyze -> artifacts -> manifest);
    3. Сохраняет ревизию в PostgreSQL и хранилище файлов;
    4. Возвращает созданную карточку испытания.

    Если csv_file не передан, CSV считается ещё не готовым: сохраняется черновик
    (Log No. + введённые метаданные + фото) со статусом ревизии "draft", без запуска
    конвейера обработки и без графика/метрик давления.
    """
    norm_log = normalize_log_no(log_no, fallback_name=Path(csv_file.filename or "report").stem if csv_file and csv_file.filename else log_no)

    # Парсинг списков труб и бандлов
    pipe_numbers = [p.strip() for p in pipe_numbers_raw.replace(",", "\n").splitlines() if p.strip()]
    # Удаление дубликатов с сохранением порядка
    pipe_numbers = list(dict.fromkeys(pipe_numbers))

    bundle_numbers = [b.strip() for b in bundle_numbers_raw.replace(",", "\n").splitlines() if b.strip()]
    bundle_numbers = list(dict.fromkeys(bundle_numbers))

    if csv_file is None or not csv_file.filename:
        return await _create_draft_revision(
            db=db,
            norm_log=norm_log,
            test_pressure=test_pressure,
            system=system,
            ins_no=ins_no,
            project=project,
            note=note,
            wika_nr=wika_nr,
            operator=operator,
            pipe_numbers=pipe_numbers,
            bundle_numbers=bundle_numbers,
            pipe_photos=pipe_photos,
            gauge_photos=gauge_photos,
            other_photos=other_photos,
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        temp_input_dir = tmp_path / "input"
        temp_input_dir.mkdir()
        temp_output_dir = tmp_path / "output"
        temp_output_dir.mkdir()

        # Сохранение CSV во временный каталог
        csv_dest = temp_input_dir / (csv_file.filename or "input.csv")
        with open(csv_dest, "wb") as f:
            shutil.copyfileobj(csv_file.file, f)

        # Сохранение и категоризация фото
        photos: List[PhotoAttachment] = []

        async def save_photos(files: List[UploadFile], cat: str):
            for pf in files:
                if pf.filename:
                    p_dest = temp_input_dir / pf.filename
                    with open(p_dest, "wb") as f:
                        shutil.copyfileobj(pf.file, f)
                    photos.append(PhotoAttachment(path=p_dest, category=cat))

        await save_photos(pipe_photos, "pipe")
        await save_photos(gauge_photos, "gauge")
        await save_photos(other_photos, "other")

        # Создание TestInput DTO
        test_input = TestInput(
            csv_path=csv_dest,
            log_no=norm_log,
            test_pressure=test_pressure,
            system=system,
            ins_no=ins_no,
            project=project,
            note=note,
            wika_nr=wika_nr,
            operator=operator,
            bundle_numbers=bundle_numbers,
            pipe_numbers=pipe_numbers,
            create_pdf=create_pdf,
            photos=photos
        )

        config = AppConfig()
        core_result = process_test_input(test_input, output_base_dir=temp_output_dir, config=config)

        if not core_result.success or not core_result.manifest_path:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"CSV processing failed: {core_result.error_message}"
            )

        with open(core_result.manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        # 5. Сохранение артефактов в хранилище storage
        log_build_dir = core_result.revision_dir
        for art in manifest_data.get("artifacts", []):
            local_art_path = log_build_dir / art["relative_path"]
            if local_art_path.exists():
                storage_key = f"logs/{norm_log}/revisions/{core_result.revision_id}/{art['relative_path']}"
                with open(local_art_path, "rb") as af:
                    storage.store_file(storage_key, af)

        # 6. Сохранение в базу данных
        test = db.query(PressureTest).filter(PressureTest.log_no == norm_log).first()
        if not test:
            test = PressureTest(log_no=norm_log)
            db.add(test)
            db.flush()

        db.query(TestRevision).filter(TestRevision.pressure_test_id == test.id).update({"is_primary": False})

        rev = TestRevision(
            pressure_test_id=test.id,
            revision_id=core_result.revision_id,
            status="complete",
            is_primary=True,
            operator=operator or "operator",
            metadata_json=manifest_data.get("metadata", {}),
            metrics_json=manifest_data.get("metrics", {})
        )
        db.add(rev)
        db.flush()

        for art in manifest_data.get("artifacts", []):
            storage_key = f"logs/{norm_log}/revisions/{core_result.revision_id}/{art['relative_path']}"
            db_art = Artifact(
                test_revision_id=rev.id,
                name=art["name"],
                relative_path=art["relative_path"],
                file_type=art["file_type"],
                category=art.get("category"),
                size_bytes=art["size_bytes"],
                sha256=art["sha256"],
                storage_key=storage_key
            )
            db.add(db_art)

        for p in pipe_numbers:
            db.add(Pipe(test_revision_id=rev.id, pipe_number=p))

        for b in bundle_numbers:
            db.add(Bundle(test_revision_id=rev.id, bundle_number=b))

        db.commit()

        # Возвращаем созданный тест с ревизиями
        return (
            db.query(PressureTest)
            .options(joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts))
            .filter(PressureTest.id == test.id)
            .first()
        )


@router.post("/package", response_model=List[PressureTestResponse])
async def upload_package_or_zip(
    package_file: Optional[UploadFile] = File(None, description="ZIP-архив с логом или ревизией"),
    files: List[UploadFile] = File([], description="Файлы из загруженной папки"),
    db: Session = Depends(get_db)
):
    """
    Универсальная загрузка испытания целой папкой или ZIP-архивом:
    - Принимает .zip архив или пачку файлов из папки;
    - Если внутри есть manifest.json, импортирует существующую ревизию;
    - Если внутри CSV и фото, автоматически обрабатывает через ядро WIKA CPG1500;
    - Возвращает обновлённый список испытаний.
    """
    import zipfile

    results: List[PressureTest] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        extracted_dir = tmp_path / "extracted"
        extracted_dir.mkdir()

        # 1. Сохранение и распаковка файлов
        if package_file and package_file.filename:
            pkg_dest = tmp_path / package_file.filename
            with open(pkg_dest, "wb") as f:
                shutil.copyfileobj(package_file.file, f)

            if package_file.filename.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(pkg_dest, "r") as zf:
                        zf.extractall(extracted_dir)
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"Invalid ZIP archive: {e}")
            elif package_file.filename.lower().endswith(".csv"):
                shutil.copy(pkg_dest, extracted_dir / package_file.filename)
            else:
                shutil.copy(pkg_dest, extracted_dir / package_file.filename)

        for f in files:
            if f.filename:
                # Keep subfolder structure if provided in filename
                raw_name = f.filename.replace("\\", "/")
                rel_parts = Path(raw_name).parts
                clean_rel = Path(*rel_parts[1:]) if len(rel_parts) > 1 else Path(raw_name)
                target = extracted_dir / clean_rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "wb") as out_f:
                    shutil.copyfileobj(f.file, out_f)

        # 2. Поиск манифестов
        manifests = list(extracted_dir.rglob("manifest.json"))
        if manifests:
            # Sort to prefer revisions or root manifest with most artifacts
            manifest_candidates = []
            for mf_path in manifests:
                try:
                    with open(mf_path, "r", encoding="utf-8") as mf_f:
                        m_data = json.load(mf_f)
                        manifest_candidates.append((mf_path, m_data, len(m_data.get("artifacts", []))))
                except Exception:
                    continue

            # Sort by number of artifacts descending so most complete revision is used
            manifest_candidates.sort(key=lambda x: x[2], reverse=True)

            if manifest_candidates:
                mf_path, manifest_data, _ = manifest_candidates[0]
                log_no = manifest_data.get("log_no") or normalize_log_no("", fallback_name=mf_path.parent.name)
                revision_id = manifest_data.get("revision_id") or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                rev_dir = mf_path.parent

                # Сохраняем в базу данных
                test = db.query(PressureTest).filter(PressureTest.log_no == log_no).first()
                if not test:
                    test = PressureTest(log_no=log_no)
                    db.add(test)
                    db.flush()
                else:
                    if test.is_archived:
                        purge_archived_test_revisions(test, db)
                    test.is_archived = False

                db.query(TestRevision).filter(TestRevision.pressure_test_id == test.id).update({"is_primary": False})
                rev = TestRevision(
                    pressure_test_id=test.id,
                    revision_id=revision_id,
                    status="complete",
                    is_primary=True,
                    metadata_json=manifest_data.get("metadata", {}),
                    metrics_json=manifest_data.get("metrics", {})
                )
                db.add(rev)
                db.flush()

                imported_relative_paths = set()

                # Process artifacts listed in manifest
                for art in manifest_data.get("artifacts", []):
                    rel_p = art["relative_path"]
                    imported_relative_paths.add(rel_p)
                    imported_relative_paths.add(art["name"])

                    # Locate file across possible locations
                    possible_paths = [
                        rev_dir / rel_p,
                        extracted_dir / rel_p,
                        extracted_dir / art["name"],
                    ]
                    art_file = next((p for p in possible_paths if p.exists()), None)
                    if not art_file:
                        art_file = next(extracted_dir.rglob(art["name"]), None)

                    storage_key = f"logs/{log_no}/revisions/{revision_id}/{rel_p}"
                    if art_file and art_file.exists():
                        with open(art_file, "rb") as af:
                            storage.store_file(storage_key, af)

                    db.add(Artifact(
                        test_revision_id=rev.id,
                        name=art["name"],
                        relative_path=rel_p,
                        file_type=art["file_type"],
                        category=art.get("category"),
                        size_bytes=art["size_bytes"],
                        sha256=art["sha256"],
                        storage_key=storage_key
                    ))

                # Auto-discover any extra photos or PDF files in folder not listed in manifest
                for extra_file in extracted_dir.rglob("*"):
                    if not extra_file.is_file() or extra_file.name == "manifest.json":
                        continue
                    if extra_file.name in imported_relative_paths:
                        continue

                    ext = extra_file.suffix.lower()
                    if ext in [".jpg", ".jpeg", ".png", ".pdf", ".xlsx", ".txt", ".csv"]:
                        calc_sha = hashlib.sha256(extra_file.read_bytes()).hexdigest()
                        calc_size = extra_file.stat().st_size

                        if ext in [".jpg", ".jpeg"]:
                            f_type = "photo"
                            cat = "gauge" if "gauge" in extra_file.name.lower() or "photo_1" in extra_file.name.lower() else ("pipe" if "pipe" in extra_file.name.lower() or "photo_2" in extra_file.name.lower() else "other")
                            rel_p = f"attached_photos/{extra_file.name}"
                        elif ext == ".png" and not extra_file.name.endswith(".png"):
                            f_type = "photo"
                            cat = "other"
                            rel_p = f"attached_photos/{extra_file.name}"
                        elif ext == ".pdf":
                            f_type = "report_pdf"
                            cat = None
                            rel_p = extra_file.name
                        elif ext == ".xlsx":
                            f_type = "excel_xlsx"
                            cat = None
                            rel_p = extra_file.name
                        elif ext == ".txt":
                            f_type = "text_txt"
                            cat = None
                            rel_p = extra_file.name
                        elif ext == ".csv":
                            f_type = "source_csv"
                            cat = None
                            rel_p = f"source/{extra_file.name}"
                        else:
                            continue

                        storage_key = f"logs/{log_no}/revisions/{revision_id}/{rel_p}"
                        with open(extra_file, "rb") as af:
                            storage.store_file(storage_key, af)

                        db.add(Artifact(
                            test_revision_id=rev.id,
                            name=extra_file.name,
                            relative_path=rel_p,
                            file_type=f_type,
                            category=cat,
                            size_bytes=calc_size,
                            sha256=calc_sha,
                            storage_key=storage_key
                        ))
                        imported_relative_paths.add(extra_file.name)

                # Добавляем трубы
                for p in manifest_data.get("metadata", {}).get("pipe_numbers", []):
                    db.add(Pipe(test_revision_id=rev.id, pipe_number=p))

                db.commit()
                results.append(test)

        else:
            # 3. Поиск исходных CSV файлов
            csv_files = list(extracted_dir.rglob("*.csv"))
            if not csv_files:
                raise HTTPException(status_code=400, detail="No CSV files or manifest.json found in the uploaded package.")

            for csv_path in csv_files:
                norm_log = normalize_log_no("", fallback_name=csv_path.stem)
                photo_files = [
                    p for p in extracted_dir.rglob("*")
                    if p.suffix.lower() in [".jpg", ".jpeg", ".png"] and p != csv_path
                ]
                photos = [PhotoAttachment(path=p, category="other") for p in photo_files]

                test_input = TestInput(
                    csv_path=csv_path,
                    log_no=norm_log,
                    photos=photos,
                    create_pdf=True
                )
                temp_out = tmp_path / f"out_{norm_log}"
                temp_out.mkdir(exist_ok=True)
                core_res = process_test_input(test_input, output_base_dir=temp_out, config=AppConfig())

                if core_res.success and core_res.manifest_path:
                    with open(core_res.manifest_path, "r", encoding="utf-8") as mf_f:
                        manifest_data = json.load(mf_f)

                    test = db.query(PressureTest).filter(PressureTest.log_no == norm_log).first()
                    if not test:
                        test = PressureTest(log_no=norm_log)
                        db.add(test)
                        db.flush()
                    else:
                        if test.is_archived:
                            purge_archived_test_revisions(test, db)
                        test.is_archived = False

                    db.query(TestRevision).filter(TestRevision.pressure_test_id == test.id).update({"is_primary": False})
                    rev = TestRevision(
                        pressure_test_id=test.id,
                        revision_id=core_res.revision_id,
                        status="complete",
                        is_primary=True,
                        metadata_json=manifest_data.get("metadata", {}),
                        metrics_json=manifest_data.get("metrics", {})
                    )
                    db.add(rev)
                    db.flush()

                    for art in manifest_data.get("artifacts", []):
                        art_file = core_res.revision_dir / art["relative_path"]
                        storage_key = f"logs/{norm_log}/revisions/{core_res.revision_id}/{art['relative_path']}"
                        if art_file.exists():
                            with open(art_file, "rb") as af:
                                storage.store_file(storage_key, af)

                        db.add(Artifact(
                            test_revision_id=rev.id,
                            name=art["name"],
                            relative_path=art["relative_path"],
                            file_type=art["file_type"],
                            category=art.get("category"),
                            size_bytes=art["size_bytes"],
                            sha256=art["sha256"],
                            storage_key=storage_key
                        ))

                    db.commit()
                    results.append(test)

    # Return refreshed test cards
    test_ids = [t.id for t in results]
    return (
        db.query(PressureTest)
        .options(joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts))
        .filter(PressureTest.id.in_(test_ids))
        .all()
    )

