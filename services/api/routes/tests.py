import io
import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from services.api.database import get_db
from services.api.models import Artifact, Bundle, Pipe, PressureTest, TestRevision, User
from services.api.schemas import (
    PipeCloudUpdateRequest,
    PipeCloudUpdateResponse,
    PressureTestResponse,
)
from services.api.storage import storage
from services.api.auth import require_role, require_authenticated_user
from services.api.audit import log_audit_event
from wika_report.models import normalize_log_no

router = APIRouter(prefix="/api/v1/tests", tags=["Pressure Tests"])


class PtrSourceResolveRequest(BaseModel):
    identifiers: List[str]


def _normalize_ptr_identifier(value: str) -> str:
    return "".join(value.strip().split()).casefold()


@router.get("/ptr-source-identifiers")
def list_ptr_source_identifiers(
    q: str = "",
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List pipe and bundle identifiers available for a PTR from active primary revisions."""
    search = f"%{q.strip()}%"
    base_filters = (
        PressureTest.is_archived == False,
        TestRevision.is_primary == True,
    )
    pipes = (
        db.query(Pipe.pipe_number)
        .join(TestRevision, Pipe.test_revision_id == TestRevision.id)
        .join(PressureTest, TestRevision.pressure_test_id == PressureTest.id)
        .filter(*base_filters, Pipe.pipe_number.ilike(search))
        .distinct()
        .order_by(Pipe.pipe_number)
        .limit(limit)
        .all()
    )
    bundles = (
        db.query(Bundle.bundle_number)
        .join(TestRevision, Bundle.test_revision_id == TestRevision.id)
        .join(PressureTest, TestRevision.pressure_test_id == PressureTest.id)
        .filter(*base_filters, Bundle.bundle_number.ilike(search))
        .distinct()
        .order_by(Bundle.bundle_number)
        .limit(limit)
        .all()
    )
    return {
        "pipes": [pipe_number for (pipe_number,) in pipes],
        "bundles": [bundle_number for (bundle_number,) in bundles],
    }


@router.post("/resolve-ptr-sources")
def resolve_ptr_sources(payload: PtrSourceResolveRequest, db: Session = Depends(get_db)):
    """Find log revisions by an exact pipe or bundle number without changing source data."""
    requested = {
        _normalize_ptr_identifier(identifier)
        for identifier in payload.identifiers
        if isinstance(identifier, str) and identifier.strip()
    }
    if not requested:
        return {"matches": [], "unmatched_identifiers": []}

    revisions = (
        db.query(TestRevision)
        .join(PressureTest)
        .options(
            joinedload(TestRevision.pressure_test),
            joinedload(TestRevision.artifacts),
            joinedload(TestRevision.pipes),
            joinedload(TestRevision.bundles),
        )
        .filter(
            PressureTest.is_archived == False,
            TestRevision.is_primary == True,
        )
        .all()
    )

    matched_identifiers = set()
    matches = []
    for revision in revisions:
        pipe_numbers = [pipe.pipe_number for pipe in revision.pipes]
        bundle_numbers = [bundle.bundle_number for bundle in revision.bundles]
        matched_pipes = [
            pipe_number for pipe_number in pipe_numbers
            if _normalize_ptr_identifier(pipe_number) in requested
        ]
        matched_bundles = [
            bundle_number for bundle_number in bundle_numbers
            if _normalize_ptr_identifier(bundle_number) in requested
        ]
        if not matched_pipes and not matched_bundles:
            continue

        matched_identifiers.update(_normalize_ptr_identifier(value) for value in matched_pipes + matched_bundles)
        selected_pipes = pipe_numbers if matched_bundles else matched_pipes
        matches.append({
            "pressure_test_id": revision.pressure_test_id,
            "test_revision_id": revision.id,
            "log_no": revision.pressure_test.log_no,
            "revision_id": revision.revision_id,
            "operator": revision.operator,
            "metadata": revision.metadata_json,
            "metrics": revision.metrics_json,
            "pipecloud_added": revision.pressure_test.pipecloud_added,
            "selected_pipe_numbers": selected_pipes,
            "matched_bundles": matched_bundles,
            "artifacts": [
                {
                    "artifact_id": artifact.id,
                    "source": "log_artifact",
                    "category": artifact.category or "other",
                    "name": artifact.name,
                    "storage_key": artifact.relative_path,
                    "sha256": artifact.sha256,
                    "position": position,
                    "is_included_in_pdf": True,
                }
                for position, artifact in enumerate(revision.artifacts)
            ],
        })

    return {
        "matches": matches,
        "unmatched_identifiers": [
            identifier for identifier in payload.identifiers
            if _normalize_ptr_identifier(identifier) not in matched_identifiers
        ],
    }


def purge_test_revisions(test: PressureTest, db: Session) -> None:
    revisions = db.query(TestRevision).filter(TestRevision.pressure_test_id == test.id).all()
    for revision in revisions:
        for artifact in revision.artifacts:
            file_path = storage.get_file_path(artifact.storage_key)
            if file_path and file_path.exists():
                file_path.unlink()
        db.delete(revision)
    
def purge_expired_trash(db: Session) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    expired = db.query(PressureTest).filter(
        PressureTest.is_archived == True,
        PressureTest.updated_at < cutoff,
    ).all()
    for test in expired:
        purge_test_revisions(test, db)
        db.delete(test)
    if expired:
        db.commit()


@router.get("", response_model=List[PressureTestResponse])
def list_or_search_pressure_tests(
    q: Optional[str] = Query(None, description="Строка поиска по Log No, Pipe No, Bundle No, оператору или проекту"),
    pipecloud_filter: Optional[str] = Query(None, description="Фильтр: all, added, not_added"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Возвращает список всех неархивированных испытаний с поддержкой интеллектуального поиска по:
    - Log No.
    - Номеру трубы (Pipe No.)
    - Номеру бандла (Bundle No.)
    - Оператору, проекту, системе, инспекционному номеру.
    - Статусу PipeCloud.
    """
    query = (
        db.query(PressureTest)
        .filter(PressureTest.is_archived == False)
        .options(
            joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts)
        )
    )

    if pipecloud_filter == "added":
        query = query.filter(PressureTest.pipecloud_added == True)
    elif pipecloud_filter == "not_added":
        query = query.filter(PressureTest.pipecloud_added == False)

    if isinstance(q, str) and q.strip():
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
    
@router.get("/trash", response_model=List[PressureTestResponse])
def list_trash(db: Session = Depends(get_db)):
    purge_expired_trash(db)
    return (
        db.query(PressureTest)
        .filter(PressureTest.is_archived == True)
        .options(joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts))
        .order_by(PressureTest.updated_at.desc())
        .all()
    )


@router.get("/{log_no}", response_model=PressureTestResponse)
def get_pressure_test_by_log(log_no: str, db: Session = Depends(get_db)):
    """Возвращает карточку испытания и историю ревизий по Log No."""
    normalized = normalize_log_no(log_no)
    test = (
        db.query(PressureTest)
        .options(joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts))
        .filter(PressureTest.log_no == normalized, PressureTest.is_archived == False)
        .first()
    )
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pressure test with Log No '{normalized}' not found."
        )
    return test


@router.patch("/{log_no}/pipecloud", response_model=PipeCloudUpdateResponse)
def update_pipecloud_status(
    log_no: str,
    payload: PipeCloudUpdateRequest,
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Ручное переключение статуса Added to PipeCloud для Pressure Test Log.
    - Идемпотентно (с поддержкой idempotency_key);
    - Доступно любому активному авторизованному сотруднику;
    - Фиксируется в неизменяемом Audit Trail;
    - Не сбрасывает и не создает новую ревизию;
    - Не изменяет доказательный хеш-манифест.
    """
    norm_log = normalize_log_no(log_no)
    test = (
        db.query(PressureTest)
        .filter(PressureTest.log_no == norm_log, PressureTest.is_archived == False)
        .first()
    )
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pressure test with Log No '{norm_log}' not found."
        )

    old_val = bool(test.pipecloud_added)
    new_val = bool(payload.added)

    test.pipecloud_added = new_val
    test.pipecloud_updated_at = datetime.now(timezone.utc)
    test.pipecloud_updated_by_user_id = str(current_user.id)
    test.pipecloud_updated_by_name = current_user.full_name or current_user.username
    db.commit()

    log_audit_event(
        db,
        action="pipecloud_status_changed",
        entity_type="pressure_test",
        entity_id=str(test.id),
        actor_id=str(current_user.id),
        actor_name=current_user.full_name or current_user.username,
        details={
            "log_no": norm_log,
            "old_value": old_val,
            "new_value": new_val,
            "idempotency_key": payload.idempotency_key,
            "source": "web"
        }
    )

    return PipeCloudUpdateResponse(
        log_no=norm_log,
        pipecloud_added=test.pipecloud_added,
        pipecloud_updated_at=test.pipecloud_updated_at,
        pipecloud_updated_by_name=test.pipecloud_updated_by_name
    )


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
    elif artifact.name.endswith(".txt") or artifact.name.endswith(".csv"):
        media_type = "text/plain; charset=utf-8"

    is_inline = artifact.name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv"))
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=artifact.name,
        content_disposition_type="inline" if is_inline else "attachment"
    )


@router.delete("/artifacts/{artifact_id}", response_model=PressureTestResponse)
def delete_artifact(
    artifact_id: str,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db),
):
    artifact = (
        db.query(Artifact)
        .join(TestRevision, Artifact.test_revision_id == TestRevision.id)
        .join(PressureTest, TestRevision.pressure_test_id == PressureTest.id)
        .filter(Artifact.id == artifact_id, PressureTest.is_archived == False)
        .first()
    )
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found.")

    file_path = storage.get_file_path(artifact.storage_key)
    if file_path and file_path.exists():
        file_path.unlink()

    test = artifact.revision.pressure_test
    artifact_name = artifact.name
    db.delete(artifact)
    db.commit()

    log_audit_event(
        db,
        action="artifact_deleted",
        entity_type="artifact",
        entity_id=str(artifact_id),
        actor_id=str(current_user.id),
        actor_name=current_user.full_name,
        details={"log_no": test.log_no, "name": artifact_name},
    )

    return (
        db.query(PressureTest)
        .options(joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts))
        .filter(PressureTest.id == test.id)
        .first()
    )


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


class TestMetadataUpdate(BaseModel):
    log_no: Optional[str] = None
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
    Редактирование метаданных испытания (Log No., оператор, проект, система, инспекционный номер, трубы):
    - Может переименовать Log No. испытания (с проверкой уникальности);
    - Обновляет поля в TestRevision и metadata_json;
    - Обновляет связанные записи Pipe и Bundle;
    - Логирует изменение в журнале аудита;
    - Возвращает обновлённую карточку испытания.
    """
    norm_log = normalize_log_no(log_no)
    test = db.query(PressureTest).filter(PressureTest.log_no == norm_log, PressureTest.is_archived == False).first()
    if not test:
        raise HTTPException(status_code=404, detail="Pressure test not found.")

    rev = (
        db.query(TestRevision)
        .filter(TestRevision.pressure_test_id == test.id, TestRevision.revision_id == revision_id)
        .first()
    )
    if not rev:
        raise HTTPException(status_code=404, detail="Revision not found.")

    # 0. Rename Log No. if requested (checked for uniqueness against other tests)
    old_log_no = None
    if payload.log_no is not None and payload.log_no.strip():
        new_norm_log = normalize_log_no(payload.log_no)
        if new_norm_log != test.log_no:
            conflict = (
                db.query(PressureTest)
                .filter(PressureTest.log_no == new_norm_log, PressureTest.id != test.id)
                .first()
            )
            if conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Log No. '{new_norm_log}' уже используется другим испытанием."
                )
            old_log_no = test.log_no
            test.log_no = new_norm_log

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
        action="test_renamed" if old_log_no else "test_metadata_updated",
        entity_type="test_revision",
        entity_id=str(rev.id),
        details={
            "log_no": test.log_no,
            "revision_id": revision_id,
            "updated_by": rev.operator,
            **({"old_log_no": old_log_no, "new_log_no": test.log_no} if old_log_no else {})
        }
    )

    db.commit()

    return (
        db.query(PressureTest)
        .options(joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts))
        .filter(PressureTest.id == test.id)
        .first()
    )


@router.delete("/{log_no}")
def delete_test(
    log_no: str,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Логическое удаление (архивация) испытания:
    - Помечает is_archived = True;
    - Сохраняет файлы в хранилище и TestRevision для целостности ссылок составных PTR;
    - Записывает событие в журнал аудита.
    """
    norm_log = normalize_log_no(log_no)
    test = db.query(PressureTest).filter(PressureTest.log_no == norm_log, PressureTest.is_archived == False).first()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Test Log_{norm_log} not found.")

    test.is_archived = True
    test.updated_at = datetime.now(timezone.utc)
    db.commit()

    log_audit_event(
        db,
        action="test_deleted",
        entity_type="pressure_test",
        entity_id=str(test.id),
        actor_id=str(current_user.id),
        actor_name=current_user.full_name,
        details={"log_no": norm_log}
    )

    return {"status": "success", "message": f"Test Log_{norm_log} deleted successfully."}

@router.post("/{log_no}/restore", response_model=PressureTestResponse)
def restore_test(
    log_no: str,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db),
):
    norm_log = normalize_log_no(log_no)
    test = db.query(PressureTest).filter(
        PressureTest.log_no == norm_log,
        PressureTest.is_archived == True,
    ).first()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Test Log_{norm_log} not found in trash.")
    if test.updated_at < datetime.now(timezone.utc) - timedelta(days=14):
        purge_test_revisions(test, db)
        db.delete(test)
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Trash retention period has expired.")
    test.is_archived = False
    test.updated_at = datetime.now(timezone.utc)
    db.commit()
    log_audit_event(
        db,
        action="test_restored",
        entity_type="pressure_test",
        entity_id=str(test.id),
        actor_id=str(current_user.id),
        actor_name=current_user.full_name,
        details={"log_no": norm_log},
    )
    return (
        db.query(PressureTest)
        .options(joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts))
        .filter(PressureTest.id == test.id)
        .first()
    )


@router.post("/{log_no}/photos", response_model=PressureTestResponse)
async def attach_photos_to_test(
    log_no: str,
    photos: List[UploadFile] = File(..., description="Фотографии манометра или труб"),
    category: str = Form("other", description="Категория: gauge, pipe, other"),
    current_user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Прикрепление фотографий (манометр, трубы) к существующему испытанию.
    """
    norm_log = normalize_log_no(log_no)
    test = db.query(PressureTest).filter(PressureTest.log_no == norm_log, PressureTest.is_archived == False).first()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Test Log_{norm_log} not found.")

    rev = db.query(TestRevision).filter(TestRevision.pressure_test_id == test.id, TestRevision.is_primary == True).first()
    if not rev:
        rev = db.query(TestRevision).filter(TestRevision.pressure_test_id == test.id).order_by(TestRevision.created_at.desc()).first()
    if not rev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No revision found for test.")

    for photo_f in photos:
        if not photo_f.filename:
            continue
        content = await photo_f.read()
        file_sha = hashlib.sha256(content).hexdigest()
        file_size = len(content)
        rel_p = f"attached_photos/{photo_f.filename}"
        storage_key = f"logs/{norm_log}/revisions/{rev.revision_id}/{rel_p}"

        storage.store_file(storage_key, io.BytesIO(content))

        cat = category
        if "gauge" in photo_f.filename.lower() or "photo_1" in photo_f.filename.lower():
            cat = "gauge"
        elif "pipe" in photo_f.filename.lower() or "photo_2" in photo_f.filename.lower():
            cat = "pipe"

        db.add(Artifact(
            test_revision_id=rev.id,
            name=photo_f.filename,
            relative_path=rel_p,
            file_type="photo",
            category=cat,
            size_bytes=file_size,
            sha256=file_sha,
            storage_key=storage_key
        ))

    db.commit()
    log_audit_event(
        db,
        action="photos_attached",
        entity_type="test_revision",
        entity_id=str(rev.id),
        actor_id=str(current_user.id),
        actor_name=current_user.full_name or current_user.username,
        details={"log_no": norm_log, "count": len(photos)}
    )

    return (
        db.query(PressureTest)
        .options(joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts))
        .filter(PressureTest.id == test.id)
        .first()
    )
