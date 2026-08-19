import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from services.api.database import get_db
from services.api.models import Artifact, Bundle, Pipe, PressureTest, TestRevision
from services.api.schemas import SyncSessionRequest, SyncSessionResponse
from services.api.storage import storage
from wika_report.models import normalize_log_no

router = APIRouter(prefix="/api/v1/sync", tags=["Synchronization"])


@router.post("/sessions", response_model=SyncSessionResponse)
def create_sync_session(req: SyncSessionRequest, db: Session = Depends(get_db)):
    """
    Шаг 1 протокола синхронизации:
    - Проверяет существование лога и ревизии;
    - Возвращает список артефактов (SHA-256), которые серверу необходимо загрузить.
    """
    manifest = req.manifest
    norm_log = normalize_log_no(manifest.log_no)

    test = db.query(PressureTest).filter(PressureTest.log_no == norm_log).first()
    if not test:
        sync_status = "new_log"
    else:
        existing_rev = db.query(TestRevision).filter(
            TestRevision.pressure_test_id == test.id,
            TestRevision.revision_id == manifest.revision_id
        ).first()
        if existing_rev:
            return SyncSessionResponse(
                status="already_synced",
                log_no=norm_log,
                revision_id=manifest.revision_id,
                missing_artifacts=[],
                receipt_id=existing_rev.id
            )
        sync_status = "new_revision"

    # Выявляем, какие файлы ещё не сохранены в хранилище
    missing_sha = []
    for art in manifest.artifacts:
        storage_key = f"logs/{norm_log}/revisions/{manifest.revision_id}/{art.relative_path}"
        if not storage.file_exists(storage_key):
            missing_sha.append(art.sha256)

    return SyncSessionResponse(
        status=sync_status,
        log_no=norm_log,
        revision_id=manifest.revision_id,
        missing_artifacts=missing_sha,
        receipt_id=None
    )


@router.post("/sessions/{revision_id}/upload")
async def upload_sync_artifact(
    revision_id: str,
    log_no: str = Form(...),
    relative_path: str = Form(...),
    sha256: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Шаг 2 протокола синхронизации:
    - Загружает отдельный артефакт в хранилище.
    """
    norm_log = normalize_log_no(log_no)
    storage_key = f"logs/{norm_log}/revisions/{revision_id}/{relative_path}"
    storage.store_file(storage_key, file.file)
    return {"status": "uploaded", "storage_key": storage_key, "sha256": sha256}


@router.post("/sessions/{revision_id}/complete")
def complete_sync_session(
    revision_id: str,
    req: SyncSessionRequest,
    db: Session = Depends(get_db)
):
    """
    Шаг 3 протокола синхронизации (Атомарная фиксация):
    - Создаёт/обновляет PressureTest;
    - Создаёт TestRevision, Artifacts, Pipes, Bundles в единой транзакции базы данных;
    - Выдаёт подтверждённый Server Receipt.
    """
    manifest = req.manifest
    norm_log = normalize_log_no(manifest.log_no)

    # 1. Поиск или создание PressureTest
    test = db.query(PressureTest).filter(PressureTest.log_no == norm_log).first()
    if not test:
        test = PressureTest(log_no=norm_log)
        db.add(test)
        db.flush()

    # Снимаем primary флаг со старых ревизий
    db.query(TestRevision).filter(TestRevision.pressure_test_id == test.id).update({"is_primary": False})

    # 2. Создание новой TestRevision
    rev = TestRevision(
        pressure_test_id=test.id,
        revision_id=manifest.revision_id,
        status="complete",
        is_primary=True,
        operator=manifest.created_by,
        metadata_json=manifest.metadata,
        metrics_json=manifest.metrics
    )
    db.add(rev)
    db.flush()

    # 3. Сохранение артефактов
    for art in manifest.artifacts:
        storage_key = f"logs/{norm_log}/revisions/{manifest.revision_id}/{art.relative_path}"
        db_art = Artifact(
            test_revision_id=rev.id,
            name=art.name,
            relative_path=art.relative_path,
            file_type=art.file_type,
            category=art.category,
            size_bytes=art.size_bytes,
            sha256=art.sha256,
            storage_key=storage_key
        )
        db.add(db_art)

    # 4. Сохранение труб и бандлов
    pipe_list = manifest.metadata.get("pipe_numbers", [])
    for p in pipe_list:
        db.add(Pipe(test_revision_id=rev.id, pipe_number=str(p)))

    bundle_list = manifest.metadata.get("bundle_numbers", [])
    for b in bundle_list:
        db.add(Bundle(test_revision_id=rev.id, bundle_number=str(b)))

    db.commit()
    db.refresh(rev)

    return {
        "status": "synced",
        "receipt_id": rev.id,
        "log_no": norm_log,
        "revision_id": rev.revision_id,
        "artifacts_count": len(manifest.artifacts)
    }
