import base64
import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, joinedload
from services.api.auth import get_current_user, require_role
from services.api.audit import log_audit_event
from services.api.config import settings
from services.api.database import get_db
from services.api.models import (
    Artifact,
    PressureTest,
    PressureTestRecord,
    PressureTestRecordItem,
    PressureTestRecordLog,
    PressureTestRecordLogArtifact,
    TestRevision,
    User,
)
from services.api.storage import storage
from wika_report.ptr_generator import (
    estimate_composite_ptr_pages,
    generate_full_composite_ptr_pdf,
    generate_ptr_pdf,
)

router = APIRouter(prefix="/api/v1/records", tags=["Pressure Test Records"])


class RecordItemCreate(BaseModel):
    item_no: int
    pipe_number: str
    drawing_no: Optional[str] = None
    spool_no: Optional[str] = None
    log_no: Optional[str] = None
    hold_start_bar: Optional[str] = None
    hold_end_bar: Optional[str] = None
    result: str = "PASS"
    notes: Optional[str] = None


class RecordItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    item_no: int
    pipe_number: str
    drawing_no: Optional[str] = None
    spool_no: Optional[str] = None
    log_no: Optional[str] = None
    hold_start_bar: Optional[str] = None
    hold_end_bar: Optional[str] = None
    result: str
    notes: Optional[str] = None


class RecordLogArtifactCreate(BaseModel):
    artifact_id: Optional[str] = None
    source: str = "log_artifact"  # log_artifact, ptr_upload, generated_from_csv
    category: str = "other"  # graph, gauge, pipe, installation, measurement_table, other
    name: str
    storage_key: Optional[str] = None
    sha256: Optional[str] = None
    position: int = 0
    is_included_in_pdf: bool = True


class RecordLogArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    record_log_id: str
    artifact_id: Optional[str] = None
    source: str
    category: str
    name: str
    storage_key: str
    sha256: str
    position: int
    is_included_in_pdf: bool
    created_at: datetime


class RecordLogCreate(BaseModel):
    pressure_test_id: str
    test_revision_id: str
    position: int = 0
    include_measurement_table: bool = True
    selected_pipe_numbers: List[str] = []
    artifacts: List[RecordLogArtifactCreate] = []


class RecordLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    record_id: str
    pressure_test_id: str
    test_revision_id: str
    position: int
    include_measurement_table: bool
    selected_pipe_numbers: List[str] = []
    metadata_snapshot: Dict[str, Any] = {}
    created_at: datetime
    artifacts: List[RecordLogArtifactResponse] = []


class RecordCustomField(BaseModel):
    label: str
    value: str


class RecordCreateRequest(BaseModel):
    record_number: str
    project: str = "ARDOR Project"
    system: str = "Piping System"
    ins_no: Optional[str] = None
    test_date: Optional[str] = None
    test_medium: str = "Water"
    design_pressure: Optional[str] = None
    test_pressure: Optional[str] = None
    duration_min: str = "60 min"
    foreman_name: Optional[str] = None
    qc_inspector: Optional[str] = None
    client_surveyor: Optional[str] = None
    notes: Optional[str] = None
    custom_fields: List[RecordCustomField] = []
    items: List[RecordItemCreate] = []
    logs: List[RecordLogCreate] = []


class RecordUpdateRequest(BaseModel):
    project: Optional[str] = None
    system: Optional[str] = None
    ins_no: Optional[str] = None
    test_date: Optional[str] = None
    test_medium: Optional[str] = None
    design_pressure: Optional[str] = None
    test_pressure: Optional[str] = None
    duration_min: Optional[str] = None
    status: Optional[str] = None
    foreman_name: Optional[str] = None
    qc_inspector: Optional[str] = None
    client_surveyor: Optional[str] = None
    notes: Optional[str] = None
    custom_fields: Optional[List[RecordCustomField]] = None
    items: Optional[List[RecordItemCreate]] = None
    logs: Optional[List[RecordLogCreate]] = None


class SignatureUploadRequest(BaseModel):
    image_base64: str


class RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    record_number: str
    project: str
    system: str
    ins_no: Optional[str] = None
    test_date: Optional[str] = None
    test_medium: str
    design_pressure: Optional[str] = None
    test_pressure: Optional[str] = None
    duration_min: str
    status: str
    foreman_name: Optional[str] = None
    qc_inspector: Optional[str] = None
    client_surveyor: Optional[str] = None
    notes: Optional[str] = None
    custom_fields: List[RecordCustomField] = []
    
    # Verification & Signature Fields
    verification_code: Optional[str] = None
    confirmed_by_name: Optional[str] = None
    confirmed_by_role: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    signature_image_path: Optional[str] = None
    signed_copy_path: Optional[str] = None
    sha256_hash: Optional[str] = None
    official_pdf_sha256: Optional[str] = None
    full_pdf_sha256: Optional[str] = None
    snapshot_json: Dict[str, Any] = {}

    created_at: datetime
    updated_at: datetime
    items: List[RecordItemResponse] = []
    logs: List[RecordLogResponse] = []


class VerificationResult(BaseModel):
    valid: bool
    verification_code: str
    record_number: str
    project: str
    system: str
    confirmed_by_name: Optional[str]
    confirmed_by_role: Optional[str]
    confirmed_at: Optional[str]
    sha256_hash: Optional[str]
    status: str


@router.get("", response_model=List[RecordResponse])
def list_records(
    q: Optional[str] = Query(None, description="Search query across record number, project, system"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Возвращает список всех документов Pressure Test Record."""
    query = (
        db.query(PressureTestRecord)
        .filter(PressureTestRecord.is_archived == False)
        .options(
            joinedload(PressureTestRecord.items),
            joinedload(PressureTestRecord.logs).joinedload(PressureTestRecordLog.artifacts)
        )
    )

    if q and q.strip():
        search = f"%{q.strip()}%"
        query = query.filter(
            (PressureTestRecord.record_number.ilike(search)) |
            (PressureTestRecord.project.ilike(search)) |
            (PressureTestRecord.system.ilike(search)) |
            (PressureTestRecord.foreman_name.ilike(search))
        )

    if status and status.lower() != "all":
        query = query.filter(PressureTestRecord.status == status.lower())

    records = query.order_by(PressureTestRecord.updated_at.desc()).offset(skip).limit(limit).all()
    return records


@router.post("", response_model=RecordResponse)
def create_record(
    req: RecordCreateRequest,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db)
):
    """Создаёт новый черновик Pressure Test Record с привязкой логов и строк труб."""
    existing = db.query(PressureTestRecord).filter(PressureTestRecord.record_number == req.record_number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Record number '{req.record_number}' already exists."
        )

    record = PressureTestRecord(
        record_number=req.record_number,
        project=req.project,
        system=req.system,
        ins_no=req.ins_no,
        test_date=req.test_date,
        test_medium=req.test_medium,
        design_pressure=req.design_pressure,
        test_pressure=req.test_pressure,
        duration_min=req.duration_min,
        status="draft",
        foreman_name=req.foreman_name or current_user.full_name,
        qc_inspector=req.qc_inspector,
        client_surveyor=req.client_surveyor,
        notes=req.notes,
        custom_fields=[field.model_dump() for field in req.custom_fields],
    )
    db.add(record)
    db.flush()

    # 1. Привязка строк труб
    for item in req.items:
        db_item = PressureTestRecordItem(
            record_id=record.id,
            item_no=item.item_no,
            pipe_number=item.pipe_number,
            drawing_no=item.drawing_no,
            spool_no=item.spool_no,
            log_no=item.log_no,
            hold_start_bar=item.hold_start_bar,
            hold_end_bar=item.hold_end_bar,
            result=item.result,
            notes=item.notes
        )
        db.add(db_item)

    # 2. Привязка логов и артефактов
    for log_req in req.logs:
        # Получаем ревизию лога для snapshot
        rev = db.query(TestRevision).filter(TestRevision.id == log_req.test_revision_id).first()
        meta_snap = {}
        if rev:
            meta_snap = {
                "operator": rev.operator,
                "metadata": rev.metadata_json,
                "metrics": rev.metrics_json,
                "created_at": rev.created_at.isoformat()
            }

        rec_log = PressureTestRecordLog(
            record_id=record.id,
            pressure_test_id=log_req.pressure_test_id,
            test_revision_id=log_req.test_revision_id,
            position=log_req.position,
            include_measurement_table=log_req.include_measurement_table,
            selected_pipe_numbers=log_req.selected_pipe_numbers,
            metadata_snapshot=meta_snap
        )
        db.add(rec_log)
        db.flush()

        for art_req in log_req.artifacts:
            db_art = None
            if art_req.artifact_id:
                db_art = db.query(Artifact).filter(Artifact.id == art_req.artifact_id).first()

            s_key = art_req.storage_key or (db_art.storage_key if db_art else "")
            sha = art_req.sha256 or (db_art.sha256 if db_art else "")

            rec_art = PressureTestRecordLogArtifact(
                record_log_id=rec_log.id,
                artifact_id=art_req.artifact_id,
                source=art_req.source,
                category=art_req.category,
                name=art_req.name,
                storage_key=s_key,
                sha256=sha,
                position=art_req.position,
                is_included_in_pdf=art_req.is_included_in_pdf,
                created_by_name=current_user.full_name
            )
            db.add(rec_art)

    db.commit()

    log_audit_event(
        db,
        entity_type="pressure_test_record",
        entity_id=record.id,
        action="created",
        actor_id=str(current_user.id),
        actor_name=current_user.full_name,
        details={"record_number": record.record_number, "items_count": len(req.items), "logs_count": len(req.logs)}
    )

    return (
        db.query(PressureTestRecord)
        .options(
            joinedload(PressureTestRecord.items),
            joinedload(PressureTestRecord.logs).joinedload(PressureTestRecordLog.artifacts)
        )
        .filter(PressureTestRecord.id == record.id)
        .first()
    )


@router.get("/{id}", response_model=RecordResponse)
def get_record(id: str, db: Session = Depends(get_db)):
    """Возвращает детальную информацию по Pressure Test Record."""
    record = (
        db.query(PressureTestRecord)
        .options(
            joinedload(PressureTestRecord.items),
            joinedload(PressureTestRecord.logs).joinedload(PressureTestRecordLog.artifacts)
        )
        .filter(PressureTestRecord.id == id, PressureTestRecord.is_archived == False)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")
    return record


@router.put("/{id}", response_model=RecordResponse)
def update_record(
    id: str,
    req: RecordUpdateRequest,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db)
):
    """Обновляет черновик Pressure Test Record. Заблокировано для подтверждённых записей."""
    record = db.query(PressureTestRecord).filter(PressureTestRecord.id == id, PressureTestRecord.is_archived == False).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

    if record.status in ("confirmed", "signed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmed or Signed Pressure Test Records cannot be modified."
        )

    update_fields = req.model_dump(exclude_unset=True)
    items_to_update = update_fields.pop("items", None)
    logs_to_update = update_fields.pop("logs", None)

    for k, v in update_fields.items():
        setattr(record, k, v)

    if items_to_update is not None:
        db.query(PressureTestRecordItem).filter(PressureTestRecordItem.record_id == id).delete()
        for it in items_to_update:
            db.add(PressureTestRecordItem(
                record_id=id,
                item_no=it["item_no"],
                pipe_number=it["pipe_number"],
                drawing_no=it.get("drawing_no"),
                spool_no=it.get("spool_no"),
                log_no=it.get("log_no"),
                hold_start_bar=it.get("hold_start_bar"),
                hold_end_bar=it.get("hold_end_bar"),
                result=it.get("result", "PASS"),
                notes=it.get("notes")
            ))

    if logs_to_update is not None:
        db.query(PressureTestRecordLog).filter(PressureTestRecordLog.record_id == id).delete()
        for l_idx, l_req in enumerate(logs_to_update):
            rev = db.query(TestRevision).filter(TestRevision.id == l_req["test_revision_id"]).first()
            meta_snap = {
                "operator": rev.operator if rev else "",
                "metadata": rev.metadata_json if rev else {},
                "metrics": rev.metrics_json if rev else {},
                "created_at": rev.created_at.isoformat() if rev and rev.created_at else ""
            }
            rec_log = PressureTestRecordLog(
                record_id=id,
                pressure_test_id=l_req["pressure_test_id"],
                test_revision_id=l_req["test_revision_id"],
                position=l_req.get("position", l_idx),
                include_measurement_table=l_req.get("include_measurement_table", True),
                selected_pipe_numbers=l_req.get("selected_pipe_numbers", []),
                metadata_snapshot=meta_snap
            )
            db.add(rec_log)
            db.flush()

            for art_req in l_req.get("artifacts", []):
                db_art = db.query(Artifact).filter(Artifact.id == art_req.get("artifact_id")).first() if art_req.get("artifact_id") else None
                s_key = art_req.get("storage_key") or (db_art.storage_key if db_art else "")
                sha = art_req.get("sha256") or (db_art.sha256 if db_art else "")

                rec_art = PressureTestRecordLogArtifact(
                    record_log_id=rec_log.id,
                    artifact_id=art_req.get("artifact_id"),
                    source=art_req.get("source", "log_artifact"),
                    category=art_req.get("category", "other"),
                    name=art_req.get("name", "Artifact"),
                    storage_key=s_key,
                    sha256=sha,
                    position=art_req.get("position", 0),
                    is_included_in_pdf=art_req.get("is_included_in_pdf", True),
                    created_by_name=current_user.full_name
                )
                db.add(rec_art)

    db.commit()

    log_audit_event(
        db,
        entity_type="pressure_test_record",
        entity_id=record.id,
        action="updated",
        actor_id=str(current_user.id),
        actor_name=current_user.full_name,
        details={"status": record.status, "updated_fields": list(update_fields.keys())}
    )

    return (
        db.query(PressureTestRecord)
        .options(
            joinedload(PressureTestRecord.items),
            joinedload(PressureTestRecord.logs).joinedload(PressureTestRecordLog.artifacts)
        )
        .filter(PressureTestRecord.id == id)
        .first()
    )


@router.delete("/{id}")
def delete_record(
    id: str,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db)
):
    """Логическое удаление (архивация) Pressure Test Record без нарушения связей."""
    record = db.query(PressureTestRecord).filter(PressureTestRecord.id == id, PressureTestRecord.is_archived == False).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

    rec_num = record.record_number
    record.is_archived = True
    db.commit()

    log_audit_event(
        db,
        entity_type="pressure_test_record",
        entity_id=id,
        action="record_archived",
        actor_id=str(current_user.id),
        actor_name=current_user.full_name,
        details={"record_number": rec_num}
    )

    return {"status": "success", "message": f"Record {rec_num} archived successfully."}


def _build_ptr_data_payloads(record: PressureTestRecord, db: Session) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Формирует нормализованные структуры данных для генераторов Official и Full PDF."""
    rec_dict = {
        "record_number": record.record_number,
        "project": record.project,
        "system": record.system,
        "ins_no": record.ins_no,
        "test_date": record.test_date,
        "test_medium": record.test_medium,
        "design_pressure": record.design_pressure,
        "test_pressure": record.test_pressure,
        "duration_min": record.duration_min,
        "status": record.status,
        "foreman_name": record.foreman_name,
        "qc_inspector": record.qc_inspector,
        "client_surveyor": record.client_surveyor,
        "notes": record.notes,
        "custom_fields": record.custom_fields or [],
        "verification_code": record.verification_code,
        "confirmed_by_name": record.confirmed_by_name,
        "confirmed_by_role": record.confirmed_by_role,
        "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
        "signature_image_path": record.signature_image_path,
        "sha256_hash": record.sha256_hash,
        "official_pdf_sha256": record.official_pdf_sha256,
        "full_pdf_sha256": record.full_pdf_sha256
    }

    items_list = [
        {
            "item_no": it.item_no,
            "pipe_number": it.pipe_number,
            "drawing_no": it.drawing_no,
            "spool_no": it.spool_no,
            "log_no": it.log_no,
            "hold_start_bar": it.hold_start_bar,
            "hold_end_bar": it.hold_end_bar,
            "result": it.result,
            "notes": it.notes
        }
        for it in sorted(record.items, key=lambda x: x.item_no)
    ]

    logs_list = []
    # If record has linked logs
    for log_rel in sorted(record.logs, key=lambda x: x.position):
        p_test = db.query(PressureTest).filter(PressureTest.id == log_rel.pressure_test_id).first()
        t_rev = db.query(TestRevision).options(joinedload(TestRevision.artifacts)).filter(TestRevision.id == log_rel.test_revision_id).first()
        
        art_items = []
        csv_file_path = None

        if t_rev:
            for art in t_rev.artifacts:
                art_p = storage.get_file_path(art.storage_key)
                art_items.append({
                    "name": art.name,
                    "file_type": art.file_type,
                    "category": art.category,
                    "file_path": str(art_p) if art_p else "",
                    "sha256": art.sha256,
                    "is_included_in_pdf": True
                })
                if art.file_type == "source_csv" or art.name.endswith(".csv"):
                    csv_file_path = str(art_p) if art_p else None

        # PTR-specific artifacts
        for p_art in log_rel.artifacts:
            art_p = storage.get_file_path(p_art.storage_key)
            art_items.append({
                "name": p_art.name,
                "file_type": "photo",
                "category": p_art.category,
                "file_path": str(art_p) if art_p else "",
                "sha256": p_art.sha256,
                "is_included_in_pdf": p_art.is_included_in_pdf
            })

        logs_list.append({
            "log_no": p_test.log_no if p_test else "N/A",
            "revision_id": t_rev.revision_id if t_rev else "1",
            "metadata": t_rev.metadata_json if t_rev else {},
            "metrics": t_rev.metrics_json if t_rev else {},
            "selected_pipe_numbers": log_rel.selected_pipe_numbers,
            "include_measurement_table": log_rel.include_measurement_table,
            "csv_path": csv_file_path,
            "artifacts": art_items
        })

    return rec_dict, items_list, logs_list


@router.post("/{id}/confirm", response_model=RecordResponse)
def confirm_record(
    id: str,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Электронное подтверждение Pressure Test Record:
    1. Генерирует Official PDF и Full Composite PDF;
    2. Вычисляет точный SHA-256 по фактическим байтам обоих PDF файлов;
    3. Создаёт уникальный Verification Code (ARDOR-VRF-XXXX-YYYY);
    4. Замораживает snapshot_json со всеми использованными TestRevision IDs и хешами файлов;
    5. Блокирует документ от любых дальнейших изменений;
    6. Записывает событие в Audit Trail.
    """
    record = db.query(PressureTestRecord).filter(PressureTestRecord.id == id, PressureTestRecord.is_archived == False).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

    if record.status in ("confirmed", "signed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Record is already confirmed.")

    # 1. Generate unique Verification Code
    short_hash = hashlib.sha256(f"{record.id}-{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:8].upper()
    vrf_code = f"ARDOR-VRF-{short_hash}-{datetime.now().year}"

    record.verification_code = vrf_code
    record.confirmed_by_user_id = str(current_user.id)
    record.confirmed_by_name = current_user.full_name or current_user.username
    record.confirmed_by_role = current_user.role
    record.confirmed_at = datetime.now(timezone.utc)
    record.status = "confirmed"

    # 2. Build PDF payloads
    rec_dict, items_list, logs_list = _build_ptr_data_payloads(record, db)

    # 3. Generate Official PDF & compute actual byte SHA-256
    official_pdf_bytes = generate_ptr_pdf(rec_dict, items_list)
    official_sha = hashlib.sha256(official_pdf_bytes).hexdigest()
    record.official_pdf_sha256 = official_sha

    # 4. Generate Full Composite PDF & compute actual byte SHA-256
    full_pdf_bytes = generate_full_composite_ptr_pdf(rec_dict, items_list, logs_list)
    full_sha = hashlib.sha256(full_pdf_bytes).hexdigest()
    record.full_pdf_sha256 = full_sha
    record.sha256_hash = official_sha

    # 5. Snapshot metadata, linked revisions & file hashes
    snapshot = {
        "record_number": record.record_number,
        "project": record.project,
        "system": record.system,
        "confirmed_by": current_user.full_name,
        "confirmed_at": record.confirmed_at.isoformat(),
        "verification_code": vrf_code,
        "official_pdf_sha256": official_sha,
        "full_pdf_sha256": full_sha,
        "linked_revisions": [
            {
                "log_no": l.get("log_no"),
                "revision_id": l.get("revision_id"),
                "artifacts": [
                    {"name": a.get("name"), "sha256": a.get("sha256")}
                    for a in l.get("artifacts", [])
                ]
            }
            for l in logs_list
        ]
    }
    record.snapshot_json = snapshot

    # Save generated PDFs to storage
    out_dir = settings.storage_dir / "records"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{record.record_number}_Official.pdf").write_bytes(official_pdf_bytes)
    (out_dir / f"{record.record_number}_Full.pdf").write_bytes(full_pdf_bytes)

    db.commit()

    log_audit_event(
        db,
        entity_type="pressure_test_record",
        entity_id=record.id,
        action="record_confirmed",
        actor_id=str(current_user.id),
        actor_name=current_user.full_name,
        details={
            "verification_code": vrf_code,
            "official_sha256": official_sha,
            "full_sha256": full_sha
        }
    )

    return (
        db.query(PressureTestRecord)
        .options(
            joinedload(PressureTestRecord.items),
            joinedload(PressureTestRecord.logs).joinedload(PressureTestRecordLog.artifacts)
        )
        .filter(PressureTestRecord.id == id)
        .first()
    )


@router.post("/{id}/unconfirm", response_model=RecordResponse)
def unconfirm_record(
    id: str,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db),
):
    record = db.query(PressureTestRecord).filter(
        PressureTestRecord.id == id,
        PressureTestRecord.is_archived == False,
    ).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")
    if record.status not in ("confirmed", "signed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Record is not confirmed.")

    old_stamp = {
        "verification_code": record.verification_code,
        "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
        "confirmed_by_name": record.confirmed_by_name,
        "official_pdf_sha256": record.official_pdf_sha256,
        "full_pdf_sha256": record.full_pdf_sha256,
    }
    record.status = "draft"
    record.verification_code = None
    record.confirmed_by_user_id = None
    record.confirmed_by_name = None
    record.confirmed_by_role = None
    record.confirmed_at = None
    record.signature_image_path = None
    record.signed_copy_path = None
    record.sha256_hash = None
    record.official_pdf_sha256 = None
    record.full_pdf_sha256 = None
    record.snapshot_json = {}
    db.commit()
    log_audit_event(
        db,
        entity_type="pressure_test_record",
        entity_id=record.id,
        action="record_confirmation_revoked",
        actor_id=str(current_user.id),
        actor_name=current_user.full_name,
        details={"record_number": record.record_number, "previous_stamp": old_stamp},
    )
    return (
        db.query(PressureTestRecord)
        .options(joinedload(PressureTestRecord.items), joinedload(PressureTestRecord.logs).joinedload(PressureTestRecordLog.artifacts))
        .filter(PressureTestRecord.id == id)
        .first()
    )


@router.post("/{id}/signature", response_model=RecordResponse)
def upload_signature(
    id: str,
    req: SignatureUploadRequest,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db)
):
    """Сохраняет нарисованную/загруженную подпись PNG для впечатывания в документ."""
    record = db.query(PressureTestRecord).filter(PressureTestRecord.id == id, PressureTestRecord.is_archived == False).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

    if record.status in ("confirmed", "signed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change signature on confirmed record.")

    img_data = req.image_base64
    if "," in img_data:
        img_data = img_data.split(",", 1)[1]

    raw_bytes = base64.b64decode(img_data)
    sig_dir = settings.storage_dir / "signatures"
    sig_dir.mkdir(parents=True, exist_ok=True)
    sig_path = sig_dir / f"sig_{record.id}.png"
    sig_path.write_bytes(raw_bytes)

    record.signature_image_path = str(sig_path)
    db.commit()

    log_audit_event(
        db,
        entity_type="pressure_test_record",
        entity_id=record.id,
        action="signature_uploaded",
        actor_id=str(current_user.id),
        actor_name=current_user.full_name,
        details={"file_size": len(raw_bytes)}
    )

    return (
        db.query(PressureTestRecord)
        .options(
            joinedload(PressureTestRecord.items),
            joinedload(PressureTestRecord.logs).joinedload(PressureTestRecordLog.artifacts)
        )
        .filter(PressureTestRecord.id == id)
        .first()
    )


@router.post("/{id}/signed-copy", response_model=RecordResponse)
async def upload_signed_copy(
    id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db)
):
    """Загружает внешний подписанный скан PDF."""
    record = db.query(PressureTestRecord).filter(PressureTestRecord.id == id, PressureTestRecord.is_archived == False).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

    copies_dir = settings.storage_dir / "signed_copies"
    copies_dir.mkdir(parents=True, exist_ok=True)
    out_file = copies_dir / f"signed_{record.record_number}.pdf"

    content = await file.read()
    out_file.write_bytes(content)

    record.signed_copy_path = str(out_file)
    record.status = "signed"
    db.commit()

    log_audit_event(
        db,
        entity_type="pressure_test_record",
        entity_id=record.id,
        action="signed_copy_uploaded",
        actor_id=str(current_user.id),
        actor_name=current_user.full_name,
        details={"filename": file.filename, "size": len(content)}
    )

    return (
        db.query(PressureTestRecord)
        .options(
            joinedload(PressureTestRecord.items),
            joinedload(PressureTestRecord.logs).joinedload(PressureTestRecordLog.artifacts)
        )
        .filter(PressureTestRecord.id == id)
        .first()
    )


@router.get("/{id}/pdf")
def export_official_record_pdf(id: str, db: Session = Depends(get_db)):
    """Генерирует и отдаёт официальный ARDOR Pressure Test Record (Official PDF)."""
    record = (
        db.query(PressureTestRecord)
        .options(
            joinedload(PressureTestRecord.items),
            joinedload(PressureTestRecord.logs).joinedload(PressureTestRecordLog.artifacts)
        )
        .filter(PressureTestRecord.id == id, PressureTestRecord.is_archived == False)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

    rec_dict, items_list, _ = _build_ptr_data_payloads(record, db)
    pdf_bytes = generate_ptr_pdf(rec_dict, items_list)
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="PTR_{record.record_number}_Official.pdf"'}
    )


@router.get("/{id}/full-pdf")
def export_full_composite_record_pdf(id: str, db: Session = Depends(get_db)):
    """Генерирует и отдаёт полный составной документ (Official + Logs + Graphs + Photos + CSV Tables)."""
    record = (
        db.query(PressureTestRecord)
        .options(
            joinedload(PressureTestRecord.items),
            joinedload(PressureTestRecord.logs).joinedload(PressureTestRecordLog.artifacts)
        )
        .filter(PressureTestRecord.id == id, PressureTestRecord.is_archived == False)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

    rec_dict, items_list, logs_list = _build_ptr_data_payloads(record, db)
    pdf_bytes = generate_full_composite_ptr_pdf(rec_dict, items_list, logs_list)
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="PTR_{record.record_number}_Full.pdf"'}
    )


@router.get("/{id}/estimate-pages")
def estimate_record_pages(id: str, db: Session = Depends(get_db)):
    """Возвращает приблизительную / точную структуру страниц Official и Full Composite PDF."""
    record = (
        db.query(PressureTestRecord)
        .options(
            joinedload(PressureTestRecord.items),
            joinedload(PressureTestRecord.logs).joinedload(PressureTestRecordLog.artifacts)
        )
        .filter(PressureTestRecord.id == id, PressureTestRecord.is_archived == False)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

    rec_dict, items_list, logs_list = _build_ptr_data_payloads(record, db)
    return estimate_composite_ptr_pages(rec_dict, items_list, logs_list)


@router.get("/verify/{verification_code}", response_model=VerificationResult)
def verify_record_code(verification_code: str, db: Session = Depends(get_db)):
    """Внутренняя верификация подлинности документа по коду подтверждения."""
    record = db.query(PressureTestRecord).filter(
        PressureTestRecord.verification_code == verification_code,
        PressureTestRecord.is_archived == False
    ).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid verification code.")

    return VerificationResult(
        valid=True,
        verification_code=record.verification_code,
        record_number=record.record_number,
        project=record.project,
        system=record.system,
        confirmed_by_name=record.confirmed_by_name,
        confirmed_by_role=record.confirmed_by_role,
        confirmed_at=record.confirmed_at.isoformat() if record.confirmed_at else None,
        sha256_hash=record.official_pdf_sha256 or record.sha256_hash,
        status=record.status
    )
