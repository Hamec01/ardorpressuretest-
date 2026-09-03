import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.api.audit import log_audit_event
from services.api.auth import require_role
from services.api.database import get_db
from services.api.models import Pipe, PlannedTestList, PlannedTestPipe, PressureTest, TestRevision, User


router = APIRouter(prefix="/api/v1/planned-tests", tags=["Planned Pressure Tests"])


class PlannedListCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class PlannedListUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class PlannedPipeBulkCreateRequest(BaseModel):
    input_text: str


class PlannedPipeUpdateRequest(BaseModel):
    pipe_number: str


def _natural_sort_key(value: str) -> Tuple[Tuple[int, object], ...]:
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", value)
        if part
    )


def _pipe_sort_key(value: str) -> str:
    return "|".join(
        f"{int(part):012d}" if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", value)
        if part
    )


def normalize_planned_pipe(value: str) -> Tuple[str, str, str]:
    normalized = re.sub(r"\s+", "", value or "").upper()
    if normalized.count("/") != 1:
        raise ValueError("Use the format bundle/pipe, for example 122355/1.")
    bundle_number, pipe_suffix = normalized.split("/", 1)
    if not bundle_number or not pipe_suffix:
        raise ValueError("Both bundle and pipe number are required.")
    return normalized, bundle_number, _pipe_sort_key(pipe_suffix)


def _completed_log_map(db: Session, pipe_numbers: List[str]) -> Dict[str, List[dict]]:
    if not pipe_numbers:
        return {}
    rows = (
        db.query(Pipe, PressureTest, TestRevision)
        .join(TestRevision, Pipe.test_revision_id == TestRevision.id)
        .join(PressureTest, TestRevision.pressure_test_id == PressureTest.id)
        .filter(
            Pipe.pipe_number.in_(pipe_numbers),
            PressureTest.is_archived == False,
            TestRevision.is_primary == True,
            TestRevision.status.in_(["complete", "confirmed"]),
        )
        .order_by(PressureTest.updated_at.desc())
        .all()
    )
    matches: Dict[str, List[dict]] = {}
    for pipe, test, revision in rows:
        entry = {
            "pressure_test_id": test.id,
            "log_no": test.log_no,
            "revision_id": revision.revision_id,
            "status": revision.status,
            "updated_at": test.updated_at.isoformat(),
            "test_pressure": revision.metadata_json.get("test_pressure"),
        }
        existing = matches.setdefault(pipe.pipe_number, [])
        if not any(item["pressure_test_id"] == entry["pressure_test_id"] for item in existing):
            existing.append(entry)
    return matches


def _pipe_response(pipe: PlannedTestPipe, matching_logs: List[dict]) -> dict:
    latest_log = matching_logs[0] if matching_logs else None
    return {
        "id": pipe.id,
        "pipe_number": pipe.pipe_number,
        "bundle_number": pipe.bundle_number,
        "status": "completed" if matching_logs else "pending",
        "matching_logs": matching_logs,
        "latest_log_no": latest_log["log_no"] if latest_log else None,
        "latest_log_at": latest_log["updated_at"] if latest_log else None,
        "latest_test_pressure": latest_log["test_pressure"] if latest_log else None,
        "created_at": pipe.created_at.isoformat(),
        "updated_at": pipe.updated_at.isoformat(),
    }


def _get_active_list(list_id: str, db: Session) -> PlannedTestList:
    planned_list = db.query(PlannedTestList).filter(
        PlannedTestList.id == list_id,
        PlannedTestList.is_archived == False,
    ).first()
    if not planned_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pressure test plan not found.")
    return planned_list


@router.get("/lists")
def list_planned_lists(q: str = "", db: Session = Depends(get_db)):
    query = db.query(PlannedTestList).filter(PlannedTestList.is_archived == False)
    if q.strip():
        search = f"%{q.strip()}%"
        query = query.filter(
            (PlannedTestList.name.ilike(search)) | (PlannedTestList.description.ilike(search))
        )
    lists = query.order_by(PlannedTestList.updated_at.desc()).all()
    pipes = db.query(PlannedTestPipe).filter(
        PlannedTestPipe.planned_test_list_id.in_([planned_list.id for planned_list in lists])
    ).all() if lists else []
    matches = _completed_log_map(db, [pipe.pipe_number for pipe in pipes])
    totals: Dict[str, Dict[str, int]] = {}
    for pipe in pipes:
        total = totals.setdefault(pipe.planned_test_list_id, {"total": 0, "completed": 0})
        total["total"] += 1
        if matches.get(pipe.pipe_number):
            total["completed"] += 1
    return [
        {
            "id": planned_list.id,
            "name": planned_list.name,
            "description": planned_list.description,
            "created_by_name": planned_list.created_by_name,
            "created_at": planned_list.created_at.isoformat(),
            "updated_at": planned_list.updated_at.isoformat(),
            "pipe_count": totals.get(planned_list.id, {}).get("total", 0),
            "completed_count": totals.get(planned_list.id, {}).get("completed", 0),
        }
        for planned_list in lists
    ]


@router.post("/lists")
def create_planned_list(
    payload: PlannedListCreateRequest,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Plan name is required.")
    planned_list = PlannedTestList(
        name=name,
        description=(payload.description or "").strip() or None,
        created_by_user_id=current_user.id,
        created_by_name=current_user.full_name or current_user.username,
    )
    db.add(planned_list)
    db.commit()
    db.refresh(planned_list)
    log_audit_event(
        db, "planned_test_list", planned_list.id, "planned_list_created",
        str(current_user.id), current_user.full_name or current_user.username,
        {"name": planned_list.name},
    )
    return {"id": planned_list.id, "name": planned_list.name, "description": planned_list.description}


@router.get("/lists/{list_id}/pipes")
def list_planned_pipes(
    list_id: str,
    q: str = "",
    bundle: str = "",
    db: Session = Depends(get_db),
):
    planned_list = _get_active_list(list_id, db)
    pipes = db.query(PlannedTestPipe).filter(PlannedTestPipe.planned_test_list_id == planned_list.id).all()
    matches = _completed_log_map(db, [pipe.pipe_number for pipe in pipes])
    search = q.strip().casefold()
    normalized_bundle = re.sub(r"\s+", "", bundle).casefold()
    result = []
    for pipe in pipes:
        pipe_logs = matches.get(pipe.pipe_number, [])
        searchable_logs = " ".join(log["log_no"] for log in pipe_logs).casefold()
        if search and search not in pipe.pipe_number.casefold() and search not in pipe.bundle_number.casefold() and search not in searchable_logs:
            continue
        if normalized_bundle and normalized_bundle not in pipe.bundle_number.casefold():
            continue
        result.append(_pipe_response(pipe, pipe_logs))
    result.sort(key=lambda item: (_natural_sort_key(item["bundle_number"]), _natural_sort_key(item["pipe_number"].rsplit("/", 1)[-1])))
    bundles: Dict[str, List[dict]] = {}
    for item in result:
        bundles.setdefault(item["bundle_number"], []).append(item)
    return {
        "list": {"id": planned_list.id, "name": planned_list.name, "description": planned_list.description},
        "summary": {"total": len(result), "completed": sum(item["status"] == "completed" for item in result)},
        "bundles": [
            {"bundle_number": bundle_number, "pipes": grouped_pipes, "completed_count": sum(item["status"] == "completed" for item in grouped_pipes)}
            for bundle_number, grouped_pipes in bundles.items()
        ],
        "pipes": result,
    }


@router.post("/lists/{list_id}/pipes/bulk")
def bulk_create_planned_pipes(
    list_id: str,
    payload: PlannedPipeBulkCreateRequest,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db),
):
    planned_list = _get_active_list(list_id, db)
    entries = [entry.strip() for entry in re.split(r"[\n,;]+", payload.input_text) if entry.strip()]
    if not entries:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter at least one pipe number.")

    parsed = []
    errors = []
    seen = set()
    for line_number, entry in enumerate(entries, start=1):
        try:
            pipe_number, bundle_number, pipe_sort_key = normalize_planned_pipe(entry)
        except ValueError as exc:
            errors.append({"line": line_number, "value": entry, "message": str(exc)})
            continue
        if pipe_number in seen:
            errors.append({"line": line_number, "value": entry, "message": "Duplicate pipe in this input."})
            continue
        seen.add(pipe_number)
        parsed.append((pipe_number, bundle_number, pipe_sort_key))
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": errors})

    existing = {
        pipe_number for (pipe_number,) in db.query(PlannedTestPipe.pipe_number).filter(
            PlannedTestPipe.planned_test_list_id == planned_list.id,
            PlannedTestPipe.pipe_number.in_([item[0] for item in parsed]),
        ).all()
    }
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Some pipes already exist in this plan.", "pipe_numbers": sorted(existing)},
        )

    for pipe_number, bundle_number, pipe_sort_key in parsed:
        db.add(PlannedTestPipe(
            planned_test_list_id=planned_list.id,
            pipe_number=pipe_number,
            bundle_number=bundle_number,
            pipe_sort_key=pipe_sort_key,
        ))
    planned_list.updated_at = datetime.now(timezone.utc)
    db.commit()
    log_audit_event(
        db, "planned_test_list", planned_list.id, "planned_pipes_added",
        str(current_user.id), current_user.full_name or current_user.username,
        {"count": len(parsed)},
    )
    return {"created_count": len(parsed)}


@router.patch("/lists/{list_id}")
def update_planned_list(
    list_id: str,
    payload: PlannedListUpdateRequest,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db),
):
    planned_list = _get_active_list(list_id, db)
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Plan name is required.")
        planned_list.name = name
    if payload.description is not None:
        planned_list.description = payload.description.strip() or None
    db.commit()
    log_audit_event(
        db, "planned_test_list", planned_list.id, "planned_list_updated",
        str(current_user.id), current_user.full_name or current_user.username,
        {"name": planned_list.name},
    )
    return {"id": planned_list.id, "name": planned_list.name, "description": planned_list.description}


@router.delete("/lists/{list_id}/bundles/{bundle_number}")
def delete_planned_bundle(
    list_id: str,
    bundle_number: str,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db),
):
    planned_list = _get_active_list(list_id, db)
    deleted_count = db.query(PlannedTestPipe).filter(
        PlannedTestPipe.planned_test_list_id == planned_list.id,
        PlannedTestPipe.bundle_number == bundle_number,
    ).delete(synchronize_session=False)
    if not deleted_count:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found in this plan.")
    db.commit()
    log_audit_event(
        db, "planned_test_list", planned_list.id, "planned_bundle_deleted",
        str(current_user.id), current_user.full_name or current_user.username,
        {"bundle_number": bundle_number, "count": deleted_count},
    )
    return {"deleted_count": deleted_count}


@router.patch("/pipes/{pipe_id}")
def update_planned_pipe(
    pipe_id: str,
    payload: PlannedPipeUpdateRequest,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db),
):
    pipe = db.query(PlannedTestPipe).join(PlannedTestList).filter(
        PlannedTestPipe.id == pipe_id,
        PlannedTestList.is_archived == False,
    ).first()
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planned pipe not found.")
    try:
        pipe_number, bundle_number, pipe_sort_key = normalize_planned_pipe(payload.pipe_number)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    duplicate = db.query(PlannedTestPipe).filter(
        PlannedTestPipe.planned_test_list_id == pipe.planned_test_list_id,
        PlannedTestPipe.pipe_number == pipe_number,
        PlannedTestPipe.id != pipe.id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This pipe already exists in the plan.")
    old_number = pipe.pipe_number
    pipe.pipe_number = pipe_number
    pipe.bundle_number = bundle_number
    pipe.pipe_sort_key = pipe_sort_key
    db.commit()
    log_audit_event(
        db, "planned_test_pipe", pipe.id, "planned_pipe_updated",
        str(current_user.id), current_user.full_name or current_user.username,
        {"old_pipe_number": old_number, "pipe_number": pipe_number},
    )
    return {"id": pipe.id, "pipe_number": pipe.pipe_number, "bundle_number": pipe.bundle_number}


@router.delete("/pipes/{pipe_id}")
def delete_planned_pipe(
    pipe_id: str,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db),
):
    pipe = db.query(PlannedTestPipe).join(PlannedTestList).filter(
        PlannedTestPipe.id == pipe_id,
        PlannedTestList.is_archived == False,
    ).first()
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planned pipe not found.")
    list_id = pipe.planned_test_list_id
    pipe_number = pipe.pipe_number
    db.delete(pipe)
    db.commit()
    log_audit_event(
        db, "planned_test_pipe", pipe_id, "planned_pipe_deleted",
        str(current_user.id), current_user.full_name or current_user.username,
        {"list_id": list_id, "pipe_number": pipe_number},
    )
    return {"status": "success"}


@router.delete("/lists/{list_id}")
def archive_planned_list(
    list_id: str,
    current_user: User = Depends(require_role(["foreman", "admin"])),
    db: Session = Depends(get_db),
):
    planned_list = _get_active_list(list_id, db)
    planned_list.is_archived = True
    db.commit()
    log_audit_event(
        db, "planned_test_list", planned_list.id, "planned_list_archived",
        str(current_user.id), current_user.full_name or current_user.username,
        {"name": planned_list.name},
    )
    return {"status": "success"}