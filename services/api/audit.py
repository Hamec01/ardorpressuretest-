import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from services.api.models import AuditEvent, User

logger = logging.getLogger("ardor_audit")


def log_audit_event(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_id: Optional[str] = None,
    actor_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> AuditEvent:
    """
    Записывает неизменяемое событие аудита в базу данных.
    
    entity_type: 'pressure_test', 'test_revision', 'user', 'sync_session'
    action: 'created', 'updated', 'synced', 'confirmed', 'status_change', 'login'
    """
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=actor_id,
        actor_name=actor_name,
        details_json=details or {}
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    logger.info(f"[AUDIT] {action.upper()} on {entity_type}:{entity_id} by {actor_name or 'system'}")
    return event
