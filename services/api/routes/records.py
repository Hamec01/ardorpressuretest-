import base64
import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, joinedload
from services.api.auth import get_current_user, require_role
from services.api.audit import log_audit_event
from services.api.config import settings
from services.api.database import get_db
from services.api.models import PressureTestRecord, PressureTestRecordItem, User
from wika_report.ptr_generator import generate_ptr_pdf

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
    items: List[RecordItemCreate] = []


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
    items: Optional[List[RecordItemCreate]] = None


class SignatureUploadRequest(BaseModel):
    image_base64: str  # data:image/png;base64,... or raw base64


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
    
    # Verification & Signature Fields
    verification_code: Optional[str] = None
    confirmed_by_name: Optional[str] = None
    confirmed_by_role: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    signature_image_path: Optional[str] = None
    signed_copy_path: Optional[str] = None
    sha256_hash: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    items: List[RecordItemResponse] = []


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
    query = db.query(PressureTestRecord).options(joinedload(PressureTestRecord.items))

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            (PressureTestRecord.record_number.ilike(term)) |
            (PressureTestRecord.project.ilike(term)) |
            (PressureTestRecord.system.ilike(term)) |
            (PressureTestRecord.foreman_name.ilike(term))
        )
    if status:
        query = query.filter(PressureTestRecord.status == status)

    records = query.order_by(PressureTestRecord.updated_at.desc()).offset(skip).limit(limit).all()
    return records


@router.get("/verify/{verification_code}", response_model=VerificationResult)
def verify_record_public(verification_code: str, db: Session = Depends(get_db)):
    """Публичная проверка подлинности подписанного акта по коду верификации."""
    record = db.query(PressureTestRecord).filter(PressureTestRecord.verification_code == verification_code.strip()).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification code not found or invalid.")

    return VerificationResult(
        valid=True,
        verification_code=record.verification_code,
        record_number=record.record_number,
        project=record.project,
        system=record.system,
        confirmed_by_name=record.confirmed_by_name,
        confirmed_by_role=record.confirmed_by_role,
        confirmed_at=record.confirmed_at.isoformat() if record.confirmed_at else None,
        sha256_hash=record.sha256_hash,
        status=record.status
    )


@router.post("", response_model=RecordResponse)
def create_record(
    req: RecordCreateRequest,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db)
):
    """Создаёт новый Pressure Test Record (доступно для Foreman и Admin)."""
    existing = db.query(PressureTestRecord).filter(PressureTestRecord.record_number == req.record_number.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Record with number '{req.record_number}' already exists."
        )

    record = PressureTestRecord(
        record_number=req.record_number.strip(),
        project=req.project,
        system=req.system,
        ins_no=req.ins_no,
        test_date=req.test_date or datetime.now().strftime("%Y-%m-%d"),
        test_medium=req.test_medium,
        design_pressure=req.design_pressure,
        test_pressure=req.test_pressure,
        duration_min=req.duration_min,
        status="draft",
        foreman_name=req.foreman_name or current_user.full_name,
        qc_inspector=req.qc_inspector,
        client_surveyor=req.client_surveyor,
        notes=req.notes
    )
    db.add(record)
    db.flush()

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

    db.commit()

    log_audit_event(
        db,
        entity_type="pressure_test_record",
        entity_id=record.id,
        action="created",
        actor_id=str(current_user.id),
        actor_name=current_user.full_name,
        details={"record_number": record.record_number, "items_count": len(req.items)}
    )

    return (
        db.query(PressureTestRecord)
        .options(joinedload(PressureTestRecord.items))
        .filter(PressureTestRecord.id == record.id)
        .first()
    )


@router.get("/{id}", response_model=RecordResponse)
def get_record(id: str, db: Session = Depends(get_db)):
    """Возвращает детальную информацию по Pressure Test Record."""
    record = (
        db.query(PressureTestRecord)
        .options(joinedload(PressureTestRecord.items))
        .filter(PressureTestRecord.id == id)
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
    """Обновляет статус и данные Pressure Test Record."""
    record = db.query(PressureTestRecord).filter(PressureTestRecord.id == id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

    update_fields = req.model_dump(exclude_unset=True)
    items_to_update = update_fields.pop("items", None)

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
        .options(joinedload(PressureTestRecord.items))
        .filter(PressureTestRecord.id == id)
        .first()
    )


@router.post("/{id}/confirm", response_model=RecordResponse)
def confirm_record(
    id: str,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Электронное аккаунтное подтверждение прорабом / инспектором с генерацией Verification Code и SHA-256 Digest.
    """
    record = db.query(PressureTestRecord).filter(PressureTestRecord.id == id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

    # Generate unique Verification Code
    short_hash = hashlib.sha256(f"{record.id}-{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:8].upper()
    vrf_code = f"ARDOR-VRF-{short_hash}-{datetime.now().year}"

    # Compute content SHA-256 hash
    content_raw = f"{record.record_number}:{record.project}:{record.system}:{record.test_pressure}:{current_user.username}"
    doc_sha = hashlib.sha256(content_raw.encode("utf-8")).hexdigest()

    record.verification_code = vrf_code
    record.confirmed_by_user_id = str(current_user.id)
    record.confirmed_by_name = current_user.full_name
    record.confirmed_by_role = current_user.role
    record.confirmed_at = datetime.now(timezone.utc)
    record.sha256_hash = doc_sha
    record.status = "confirmed"

    db.commit()

    log_audit_event(
        db,
        entity_type="pressure_test_record",
        entity_id=record.id,
        action="confirmed",
        actor_id=str(current_user.id),
        actor_name=current_user.full_name,
        details={"verification_code": vrf_code, "sha256": doc_sha}
    )

    return (
        db.query(PressureTestRecord)
        .options(joinedload(PressureTestRecord.items))
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
    record = db.query(PressureTestRecord).filter(PressureTestRecord.id == id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

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
        .options(joinedload(PressureTestRecord.items))
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
    record = db.query(PressureTestRecord).filter(PressureTestRecord.id == id).first()
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
        .options(joinedload(PressureTestRecord.items))
        .filter(PressureTestRecord.id == id)
        .first()
    )


@router.get("/{id}/pdf")
def export_record_pdf(id: str, db: Session = Depends(get_db)):
    """Генерирует и скачивает официальный PDF Pressure Test Record с цифровым штампом."""
    record = (
        db.query(PressureTestRecord)
        .options(joinedload(PressureTestRecord.items))
        .filter(PressureTestRecord.id == id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

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
        "verification_code": record.verification_code,
        "confirmed_by_name": record.confirmed_by_name,
        "confirmed_by_role": record.confirmed_by_role,
        "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
        "signature_image_path": record.signature_image_path,
        "sha256_hash": record.sha256_hash
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

    pdf_bytes = generate_ptr_pdf(rec_dict, items_list)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{record.record_number}_Record.pdf"'}
    )
