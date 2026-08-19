import json
import logging
import shutil
import tempfile
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


@router.post("", response_model=PressureTestResponse)
async def process_csv_web(
    csv_file: UploadFile = File(..., description="CSV-файл манометра WIKA CPG1500"),
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
    """
    norm_log = normalize_log_no(log_no, fallback_name=Path(csv_file.filename or "report").stem)

    # Парсинг списков труб и бандлов
    pipe_numbers = [p.strip() for p in pipe_numbers_raw.replace(",", "\n").splitlines() if p.strip()]
    # Удаление дубликатов с сохранением порядка
    pipe_numbers = list(dict.fromkeys(pipe_numbers))

    bundle_numbers = [b.strip() for b in bundle_numbers_raw.replace(",", "\n").splitlines() if b.strip()]
    bundle_numbers = list(dict.fromkeys(bundle_numbers))

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
