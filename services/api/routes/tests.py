import io
import zipfile
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from services.api.database import get_db
from services.api.models import Artifact, Bundle, Pipe, PressureTest, TestRevision
from services.api.schemas import PressureTestResponse
from services.api.storage import storage
from wika_report.models import normalize_log_no

router = APIRouter(prefix="/api/v1/tests", tags=["Pressure Tests"])


@router.get("", response_model=List[PressureTestResponse])
def list_or_search_pressure_tests(
    q: Optional[str] = Query(None, description="Строка поиска по Log No, Pipe No, Bundle No, оператору или проекту"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Возвращает список всех испытаний с поддержкой интеллектуального поиска по:
    - Log No.
    - Номеру трубы (Pipe No.)
    - Номеру бандла (Bundle No.)
    - Оператору, проекту, системе, инспекционному номеру.
    """
    query = db.query(PressureTest).options(
        joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts)
    )

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        
        # Подзапрос поиска ревизий по трубам и бандлам
        matching_revision_ids = (
            db.query(TestRevision.pressure_test_id)
            .outerjoin(Pipe, Pipe.test_revision_id == TestRevision.id)
            .outerjoin(Bundle, Bundle.test_revision_id == TestRevision.id)
            .filter(
                or_(
                    Pipe.pipe_number.ilike(search_term),
                    Bundle.bundle_number.ilike(search_term),
                    TestRevision.operator.ilike(search_term),
                    TestRevision.revision_id.ilike(search_term)
                )
            )
            .distinct()
            .subquery()
        )

        query = query.filter(
            or_(
                PressureTest.log_no.ilike(search_term),
                PressureTest.id.in_(matching_revision_ids)
            )
        )

    tests = query.order_by(PressureTest.updated_at.desc()).offset(skip).limit(limit).all()
    return tests


@router.get("/{log_no}", response_model=PressureTestResponse)
def get_pressure_test_by_log(log_no: str, db: Session = Depends(get_db)):
    """Возвращает карточку испытания и историю ревизий по Log No."""
    normalized = normalize_log_no(log_no)
    test = (
        db.query(PressureTest)
        .options(joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts))
        .filter(PressureTest.log_no == normalized)
        .first()
    )
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pressure test with Log No '{normalized}' not found."
        )
    return test


@router.get("/artifacts/{artifact_id}/file")
def get_artifact_file(artifact_id: str, db: Session = Depends(get_db)):
    """Отдаёт бинарное содержимое артефакта (график PNG, XLSX, PDF, фото, CSV)."""
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found.")

    file_path = storage.get_file_path(artifact.storage_key)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file missing from storage.")

    media_type = "application/octet-stream"
    if artifact.name.endswith(".png"):
        media_type = "image/png"
    elif artifact.name.endswith(".pdf"):
        media_type = "application/pdf"
    elif artifact.name.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif artifact.name.endswith(".txt") or artifact.name.endswith(".csv"):
        media_type = "text/plain; charset=utf-8"

    return FileResponse(path=file_path, media_type=media_type, filename=artifact.name)


@router.get("/{log_no}/revisions/{revision_id}/zip")
def download_revision_zip(log_no: str, revision_id: str, db: Session = Depends(get_db)):
    """Генерирует и отдаёт ZIP-архив со всеми артефактами указанной ревизии."""
    norm_log = normalize_log_no(log_no)
    rev = (
        db.query(TestRevision)
        .join(PressureTest)
        .options(joinedload(TestRevision.artifacts))
        .filter(PressureTest.log_no == norm_log, TestRevision.revision_id == revision_id)
        .first()
    )
    if not rev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for art in rev.artifacts:
            art_path = storage.get_file_path(art.storage_key)
            if art_path and art_path.exists():
                zip_file.write(art_path, arcname=art.name)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="Log_{norm_log}_{revision_id}.zip"'}
    )


from pydantic import BaseModel

class TestMetadataUpdate(BaseModel):
    operator: Optional[str] = None
    project: Optional[str] = None
    system: Optional[str] = None
    ins_no: Optional[str] = None
    test_pressure: Optional[str] = None
    wika_nr: Optional[str] = None
    note: Optional[str] = None
    pipe_numbers: Optional[List[str]] = None
    bundle_numbers: Optional[List[str]] = None


@router.put("/{log_no}/revisions/{revision_id}/metadata", response_model=PressureTestResponse)
def update_revision_metadata(
    log_no: str,
    revision_id: str,
    payload: TestMetadataUpdate,
    db: Session = Depends(get_db)
):
    """
    Редактирование метаданных испытания (оператор, проект, система, инспекционный номер, трубы):
    - Обновляет поля в TestRevision и metadata_json;
    - Обновляет связанные записи Pipe и Bundle;
    - Логирует изменение в журнале аудита;
    - Возвращает обновлённую карточку испытания.
    """
    from services.api.routes.auth import log_audit_event
    import json

    norm_log = normalize_log_no(log_no)
    test = db.query(PressureTest).filter(PressureTest.log_no == norm_log).first()
    if not test:
        raise HTTPException(status_code=404, detail="Pressure test not found.")

    rev = (
        db.query(TestRevision)
        .filter(TestRevision.pressure_test_id == test.id, TestRevision.revision_id == revision_id)
        .first()
    )
    if not rev:
        raise HTTPException(status_code=404, detail="Revision not found.")

    # 1. Update metadata json
    meta = dict(rev.metadata_json or {})
    if payload.operator is not None:
        rev.operator = payload.operator.strip()
        meta["operator"] = payload.operator.strip()
    if payload.project is not None:
        meta["project"] = payload.project.strip()
    if payload.system is not None:
        meta["system"] = payload.system.strip()
    if payload.ins_no is not None:
        meta["ins_no"] = payload.ins_no.strip()
    if payload.test_pressure is not None:
        meta["test_pressure"] = payload.test_pressure.strip()
    if payload.wika_nr is not None:
        meta["wika_nr"] = payload.wika_nr.strip()
    if payload.note is not None:
        meta["note"] = payload.note.strip()

    if payload.pipe_numbers is not None:
        meta["pipe_numbers"] = payload.pipe_numbers
        # Recreate pipes in db
        db.query(Pipe).filter(Pipe.test_revision_id == rev.id).delete()
        for p in payload.pipe_numbers:
            if p.strip():
                db.add(Pipe(test_revision_id=rev.id, pipe_number=p.strip()))

    if payload.bundle_numbers is not None:
        meta["bundle_numbers"] = payload.bundle_numbers
        # Recreate bundles in db
        db.query(Bundle).filter(Bundle.test_revision_id == rev.id).delete()
        for b in payload.bundle_numbers:
            if b.strip():
                db.add(Bundle(test_revision_id=rev.id, bundle_number=b.strip()))

    rev.metadata_json = meta

    # 2. Update stored manifest file if present in storage
    manifest_art = db.query(Artifact).filter(
        Artifact.test_revision_id == rev.id,
        Artifact.name == "manifest.json"
    ).first()
    if manifest_art:
        mf_path = storage.get_file_path(manifest_art.storage_key)
        if mf_path and mf_path.exists():
            try:
                with open(mf_path, "r", encoding="utf-8") as mf_in:
                    mf_data = json.load(mf_in)
                mf_data["metadata"] = meta
                with open(mf_path, "w", encoding="utf-8") as mf_out:
                    json.dump(mf_data, mf_out, indent=2, ensure_ascii=False)
            except Exception:
                pass

    log_audit_event(
        db,
        action="test_metadata_updated",
        entity_type="test_revision",
        entity_id=str(rev.id),
        details={"log_no": norm_log, "revision_id": revision_id, "updated_by": rev.operator}
    )

    db.commit()

    return (
        db.query(PressureTest)
        .options(joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts))
        .filter(PressureTest.id == test.id)
        .first()
    )

