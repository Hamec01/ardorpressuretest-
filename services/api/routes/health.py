from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from services.api.config import settings
from services.api.database import get_db
from services.api.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
@router.get("/api/v1/health", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)):
    """Health check endpoint to verify API and database connectivity."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        version=settings.app_version,
        database=db_status
    )
