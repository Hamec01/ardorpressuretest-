from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from services.api.auth import require_role
from services.api.database import get_db
from services.api.models import AuditEvent, User

router = APIRouter(prefix="/api/v1/audit", tags=["Audit Logs"])


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    action: str
    user_id: Optional[str] = None
    actor_name: Optional[str] = None
    details_json: Dict[str, Any]
    created_at: datetime


@router.get("", response_model=List[AuditEventResponse])
def get_audit_logs(
    entity_type: Optional[str] = Query(None, description="Фильтр по типу сущности"),
    entity_id: Optional[str] = Query(None, description="Фильтр по ID сущности"),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(require_role(["admin", "foreman"])),
    db: Session = Depends(get_db)
):
    """
    Возвращает неизменяемый журнал аудита событий (доступно для Foreman и Admin).
    """
    query = db.query(AuditEvent)
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditEvent.entity_id == entity_id)

    events = query.order_by(AuditEvent.created_at.desc()).offset(skip).limit(limit).all()
    return events
