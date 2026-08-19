import io
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, joinedload
from services.api.auth import get_current_user, require_role
from services.api.audit import log_audit_event
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
    created_at: datetime
    updated_at: datetime
    items: List[RecordItemResponse] = []


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


@router.get("/{id}/pdf")
def export_record_pdf(id: str, db: Session = Depends(get_db)):
    """Генерирует и скачивает официальный PDF Pressure Test Record."""
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
        "notes": record.notes
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
