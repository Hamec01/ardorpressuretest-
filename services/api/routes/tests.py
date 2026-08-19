from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from services.api.database import get_db
from services.api.models import PressureTest, TestRevision
from services.api.schemas import PressureTestResponse
from wika_report.models import normalize_log_no

router = APIRouter(prefix="/api/v1/tests", tags=["Pressure Tests"])


@router.get("", response_model=List[PressureTestResponse])
def list_pressure_tests(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Возвращает список всех зарегистрированных испытаний с их ревизиями."""
    tests = (
        db.query(PressureTest)
        .options(joinedload(PressureTest.revisions).joinedload(TestRevision.artifacts))
        .offset(skip)
        .limit(limit)
        .all()
    )
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
