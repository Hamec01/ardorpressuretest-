from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    database: str = "connected"


class ArtifactSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    relative_path: str
    file_type: str
    category: Optional[str] = None
    size_bytes: int
    sha256: str


class RevisionManifestUpload(BaseModel):
    manifest_version: str = "1.0"
    core_version: str = "1.0.0"
    log_no: str
    revision_id: str
    created_at_utc: str
    created_by: str = "operator"
    metadata: Dict[str, Any] = {}
    metrics: Dict[str, Any] = {}
    artifacts: List[ArtifactSchema] = []


class RevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    revision_id: str
    status: str
    is_primary: bool
    operator: str
    metadata_json: Dict[str, Any]
    metrics_json: Dict[str, Any]
    artifacts: List[ArtifactSchema]
    created_at: datetime


class PressureTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    log_no: str
    created_at: datetime
    updated_at: datetime
    revisions: List[RevisionResponse] = []


class SyncSessionRequest(BaseModel):
    idempotency_key: str
    manifest: RevisionManifestUpload


class SyncSessionResponse(BaseModel):
    status: str  # "new_log", "new_revision", "already_synced"
    log_no: str
    revision_id: str
    missing_artifacts: List[str]  # sha256 of missing files
    receipt_id: Optional[str] = None
