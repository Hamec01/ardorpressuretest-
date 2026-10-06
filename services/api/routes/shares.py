"""Public share links for pressure test logs (ADR-005 §10, docs/ACCESS_PLAN_R4-R7.md stage 2).

Management (create / list / revoke) is for admin and foreman. The /api/v1/public/*
routes need no session: the link token is the authorisation and grants exactly one
log - its current revision's data and files - and nothing else. Unknown, revoked and
foreign requests all get the same 404.
"""
import io
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.orm import Session

from services.api.auth import require_role
from services.api.config import settings
from services.api.database import get_db
from services.api.models import Artifact, AuditEvent, PressureTest, PublicShare, TestRevision, User
from services.api.shares import legacy_share_url, share_id_from_token, share_token, share_url
from services.api.storage import storage
from wika_report.models import normalize_log_no

router = APIRouter(tags=["Shares"])

PUBLIC_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
}
# Metadata a guest may see - an explicit list, never the whole internal metadata_json.
PUBLIC_METADATA_FIELDS = (
    "test_pressure", "system", "project", "ins_no", "wika_nr", "note", "date",
    "pipe_numbers", "bundle_numbers",
)

writer = require_role(["admin", "foreman"])


# ---------- schemas ----------

class ShareCreateRequest(BaseModel):
    log_no: str = Field(min_length=1, max_length=64)


class ShareResponse(BaseModel):
    id: str
    url: str
    legacy: bool
    created_at: datetime
    created_by_name: Optional[str]
    last_accessed_at: Optional[datetime]
    access_count: int


class PublicArtifact(BaseModel):
    id: str
    name: str
    file_type: str
    category: Optional[str]
    size_bytes: int
    sha256: str


class PublicRevision(BaseModel):
    revision_id: str
    status: str
    operator: Optional[str]
    created_at: datetime
    metadata: Dict[str, Any]
    metrics: Dict[str, Any]
    artifacts: List[PublicArtifact]


class PublicLog(BaseModel):
    log_no: str
    pipecloud_added: bool
    revision: Optional[PublicRevision]


class LegacyShareResolution(BaseModel):
    token: str


# ---------- helpers ----------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link is invalid or has been revoked")


def _share_response(db: Session, share: PublicShare, test: PressureTest) -> ShareResponse:
    author = db.get(User, share.created_by_user_id) if share.created_by_user_id else None
    return ShareResponse(
        id=share.id,
        url=legacy_share_url(test.log_no) if share.legacy_log_no_access else share_url(share.id),
        legacy=share.legacy_log_no_access,
        created_at=share.created_at,
        created_by_name=(author.full_name or author.username) if author else None,
        last_accessed_at=share.last_accessed_at,
        access_count=share.access_count,
    )


def _visible_shares(db: Session, test: PressureTest) -> List[PublicShare]:
    query = db.query(PublicShare).filter(
        PublicShare.pressure_test_id == test.id,
        PublicShare.revoked_at.is_(None),
    )
    if not settings.legacy_share_links:
        query = query.filter(PublicShare.legacy_log_no_access.is_(False))
    return query.order_by(PublicShare.legacy_log_no_access.asc(), PublicShare.created_at.desc()).all()


def _get_test(db: Session, log_no: str) -> PressureTest:
    test = db.query(PressureTest).filter(PressureTest.log_no == normalize_log_no(log_no)).first()
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log not found")
    return test


def _audit(db: Session, actor: User, test: PressureTest, action: str, details: dict) -> None:
    db.add(AuditEvent(
        entity_type="pressure_test",
        entity_id=str(test.id),
        action=action,
        user_id=str(actor.id),
        actor_name=actor.full_name or actor.username,
        details_json={"log_no": test.log_no, **details},
    ))


def _current_revision(test: PressureTest) -> Optional[TestRevision]:
    """The revision a guest sees: the primary one, else the newest non-archived one."""
    revisions = [rev for rev in test.revisions if rev.status != "archived"]
    primary = [rev for rev in revisions if rev.is_primary]
    candidates = primary or revisions
    return max(candidates, key=lambda rev: rev.created_at) if candidates else None


def _resolve_public(db: Session, token: str) -> tuple[PublicShare, PressureTest]:
    share_id = share_id_from_token(token)
    share = db.get(PublicShare, share_id) if share_id else None
    if share is None or share.revoked_at is not None:
        raise _not_found()
    if share.legacy_log_no_access and not settings.legacy_share_links:
        raise _not_found()
    test = db.get(PressureTest, share.pressure_test_id)
    if test is None or test.is_archived:
        raise _not_found()
    return share, test


# ---------- management (admin / foreman) ----------

@router.post("/api/v1/shares", response_model=ShareResponse)
def create_share(req: ShareCreateRequest, actor: User = Depends(writer), db: Session = Depends(get_db)):
    """Create the public token link of a log, or return the existing active one."""
    test = _get_test(db, req.log_no)
    if test.is_archived:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Restore the log before sharing it")
    share = (
        db.query(PublicShare)
        .filter(
            PublicShare.pressure_test_id == test.id,
            PublicShare.legacy_log_no_access.is_(False),
            PublicShare.revoked_at.is_(None),
        )
        .order_by(PublicShare.created_at.desc())
        .first()
    )
    if share is None:
        share = PublicShare(
            resource_type="log",
            pressure_test_id=test.id,
            legacy_log_no_access=False,
            created_by_user_id=str(actor.id),
            created_at=_now(),
            access_count=0,
        )
        db.add(share)
        db.flush()
        _audit(db, actor, test, "share_created", {"share_id": share.id})
        db.commit()
        db.refresh(share)
    return _share_response(db, share, test)


@router.get("/api/v1/shares", response_model=List[ShareResponse])
def list_shares(log_no: str = Query(..., min_length=1, max_length=64), actor: User = Depends(writer), db: Session = Depends(get_db)):
    """Active public links of a log: the token link and, for older logs, the legacy number link."""
    test = _get_test(db, log_no)
    return [_share_response(db, share, test) for share in _visible_shares(db, test)]


@router.delete("/api/v1/shares/{share_id}", response_model=ShareResponse)
def revoke_share(share_id: str, actor: User = Depends(writer), db: Session = Depends(get_db)):
    """Revoke a public link (logical: the row is kept for the audit trail)."""
    share = db.get(PublicShare, share_id)
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    test = db.get(PressureTest, share.pressure_test_id)
    if share.revoked_at is None:
        share.revoked_at = _now()
        share.revoked_by_user_id = str(actor.id)
        _audit(db, actor, test, "share_revoked", {"share_id": share.id, "legacy": share.legacy_log_no_access})
        db.commit()
        db.refresh(share)
    return _share_response(db, share, test)


# ---------- public (no session) ----------

@router.get("/api/v1/public/shares/{token}", response_model=PublicLog)
def get_public_log(token: str, response: Response, db: Session = Depends(get_db)):
    """The shared log as a guest sees it: explicit fields of its current revision only."""
    share, test = _resolve_public(db, token)
    db.execute(
        update(PublicShare)
        .where(PublicShare.id == share.id)
        .values(access_count=PublicShare.access_count + 1, last_accessed_at=_now())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    response.headers.update(PUBLIC_HEADERS)

    rev = _current_revision(test)
    revision = None
    if rev is not None:
        metadata = rev.metadata_json or {}
        revision = PublicRevision(
            revision_id=rev.revision_id,
            status=rev.status,
            operator=rev.operator,
            created_at=rev.created_at,
            metadata={key: metadata[key] for key in PUBLIC_METADATA_FIELDS if key in metadata},
            metrics=rev.metrics_json or {},
            artifacts=[
                PublicArtifact(
                    id=art.id, name=art.name, file_type=art.file_type, category=art.category,
                    size_bytes=art.size_bytes, sha256=art.sha256,
                )
                for art in rev.artifacts
            ],
        )
    return PublicLog(log_no=test.log_no, pipecloud_added=bool(test.pipecloud_added), revision=revision)


@router.get("/api/v1/public/shares/{token}/artifacts/{artifact_id}")
def get_public_artifact(token: str, artifact_id: str, db: Session = Depends(get_db)):
    """A file of the shared log's current revision; any other artifact id is 404."""
    _, test = _resolve_public(db, token)
    rev = _current_revision(test)
    artifact = next((art for art in (rev.artifacts if rev else []) if art.id == artifact_id), None)
    if artifact is None:
        raise _not_found()
    file_path = storage.get_file_path(artifact.storage_key)
    if not file_path or not file_path.exists():
        raise _not_found()
    name = artifact.name.lower()
    media_type = "application/octet-stream"
    if name.endswith(".png"):
        media_type = "image/png"
    elif name.endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif name.endswith(".pdf"):
        media_type = "application/pdf"
    elif name.endswith((".txt", ".csv")):
        media_type = "text/plain; charset=utf-8"
    inline = name.endswith((".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv"))
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=artifact.name,
        content_disposition_type="inline" if inline else "attachment",
        headers=PUBLIC_HEADERS,
    )


@router.get("/api/v1/public/shares/{token}/zip")
def get_public_zip(token: str, db: Session = Depends(get_db)):
    """ZIP of every file of the shared log's current revision."""
    _, test = _resolve_public(db, token)
    rev = _current_revision(test)
    if rev is None:
        raise _not_found()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for art in rev.artifacts:
            path = storage.get_file_path(art.storage_key)
            if path and path.exists():
                archive.write(path, arcname=art.name)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={**PUBLIC_HEADERS, "Content-Disposition": f'attachment; filename="Log_{test.log_no}.zip"'},
    )


@router.get("/api/v1/public/legacy/{log_no}", response_model=LegacyShareResolution)
def resolve_legacy_share(log_no: str, response: Response, db: Session = Depends(get_db)):
    """Old /share/{log_no} URL: only logs that kept their legacy link (existed before token links)."""
    if not settings.legacy_share_links:
        raise _not_found()
    test = db.query(PressureTest).filter(PressureTest.log_no == normalize_log_no(log_no)).first()
    if test is None or test.is_archived:
        raise _not_found()
    share = (
        db.query(PublicShare)
        .filter(
            PublicShare.pressure_test_id == test.id,
            PublicShare.legacy_log_no_access.is_(True),
            PublicShare.revoked_at.is_(None),
        )
        .first()
    )
    if share is None:
        raise _not_found()
    response.headers.update(PUBLIC_HEADERS)
    return LegacyShareResolution(token=share_token(share.id))
