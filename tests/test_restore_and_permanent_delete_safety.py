"""R1b regression guard:
- restore_test() must restore an old archived log (no age-based purge/410 Gone) as
  long as there is no active Log No. conflict, and its conflict message must not
  suggest permanent deletion.
- permanently_delete_test() is admin-only and deletes only archived logs, their files,
  and their shares; PTR-linked logs are protected.
- delete_artifact() is admin-only for unreferenced photo attachments.

Isolated by design, same pattern as test_trash_read_only.py: a private in-memory
SQLite session is used directly, never the process-wide engine, and the storage
singleton's base_path is monkeypatched to pytest's own tmp_path. DATABASE_URL /
STORAGE_DIR must still be exported to isolated temporary values by the caller,
because services.api.config.Settings() is constructed at first import time.
"""
import os

_db_url = os.environ.get("DATABASE_URL", "")
_storage_dir = os.environ.get("STORAGE_DIR", "")

if not _db_url or "5432" in _db_url or "postgres" in _db_url.lower() or "ardor_pressure_test" in _db_url:
    raise RuntimeError(
        "DATABASE_URL is missing or looks like the staging Postgres target. "
        "Export an isolated temporary DATABASE_URL before running this test."
    )
if not _storage_dir or os.path.normpath(_storage_dir) == "/data/storage":
    raise RuntimeError(
        "STORAGE_DIR is missing or points at the staging storage volume (/data/storage). "
        "Export an isolated temporary STORAGE_DIR before running this test."
    )

import pytest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.database import Base
from services.api.models import (
    Artifact, AuditEvent, Bundle, Pipe, PressureTest, PressureTestRecord,
    PressureTestRecordLog, PressureTestRecordLogArtifact, PublicShare,
    TestRevision as RevisionModel, User,
)
from services.api.auth import hash_password
from services.api.routes.tests import restore_test, permanently_delete_test, delete_artifact
from services.api import storage as storage_module


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    # PressureTest.uq_pressure_tests_active_log_no uses postgresql_where=... (a partial
    # index: unique log_no only among non-archived rows). SQLite ignores the Postgres-only
    # clause and creates a full unique index instead, which would incorrectly forbid an
    # archived log and an active log sharing a log_no - a case Postgres allows by design
    # and that restore_test()'s conflict check exists specifically to handle. Drop it here
    # so this isolated engine matches real Postgres constraint semantics.
    with engine.connect() as conn:
        conn.execute(text("DROP INDEX IF EXISTS uq_pressure_tests_active_log_no"))
        conn.commit()
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def foreman_user(db_session):
    u = User(
        username="foreman_test",
        hashed_password=hash_password("irrelevant"),
        full_name="Test Foreman",
        role="foreman",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture()
def admin_user(db_session):
    u = User(
        username="admin_test",
        hashed_password=hash_password("irrelevant"),
        full_name="Test Admin",
        role="admin",
        is_active=True,
    )
    db_session.add(u)
    db_session.commit()
    return u


def _archived_test_with_artifact(db_session, tmp_path, log_no, age_days):
    """Creates an archived PressureTest + TestRevision + Artifact backed by a real file."""
    old_timestamp = datetime.now(timezone.utc) - timedelta(days=age_days)

    test = PressureTest(log_no=log_no, is_archived=True)
    db_session.add(test)
    db_session.commit()
    db_session.query(PressureTest).filter(PressureTest.id == test.id).update(
        {"updated_at": old_timestamp}
    )
    db_session.commit()

    revision = RevisionModel(
        pressure_test_id=test.id,
        revision_id="r1",
        status="complete",
        is_primary=True,
    )
    db_session.add(revision)
    db_session.commit()

    artifact_relpath = f"logs/{log_no}/revisions/r1/report.pdf"
    artifact_file = tmp_path / artifact_relpath
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_bytes(b"regression-test placeholder bytes")

    artifact = Artifact(
        test_revision_id=revision.id,
        name="report.pdf",
        relative_path=artifact_relpath,
        file_type="report_pdf",
        size_bytes=artifact_file.stat().st_size,
        sha256="0" * 64,
        storage_key=artifact_relpath,
    )
    db_session.add(artifact)
    db_session.commit()

    return test, revision, artifact, artifact_file


def test_restore_old_archived_log_without_conflict_succeeds(db_session, tmp_path, monkeypatch, foreman_user):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)

    # Far older than the removed 14-day threshold - proves the age-based purge path is gone.
    test, revision, artifact, artifact_file = _archived_test_with_artifact(
        db_session, tmp_path, "RESTORE-OLD-1", age_days=90
    )
    test_id, revision_id, artifact_id = test.id, revision.id, artifact.id

    result = restore_test(log_no="RESTORE-OLD-1", current_user=foreman_user, db=db_session)

    assert result.is_archived is False

    # Nothing purged: same rows, same file.
    assert db_session.query(PressureTest).filter(PressureTest.id == test_id).count() == 1
    assert db_session.query(RevisionModel).filter(RevisionModel.id == revision_id).count() == 1
    assert db_session.query(Artifact).filter(Artifact.id == artifact_id).count() == 1
    assert artifact_file.exists()

    restored = db_session.query(PressureTest).filter(PressureTest.id == test_id).first()
    assert restored.is_archived is False


def test_restore_conflict_message_does_not_suggest_permanent_delete(db_session, tmp_path, monkeypatch, foreman_user):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)

    archived, revision, artifact, artifact_file = _archived_test_with_artifact(
        db_session, tmp_path, "RESTORE-CONFLICT-1", age_days=90
    )
    active = PressureTest(log_no="RESTORE-CONFLICT-1", is_archived=False)
    db_session.add(active)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        restore_test(log_no="RESTORE-CONFLICT-1", current_user=foreman_user, db=db_session)

    assert exc_info.value.status_code == 409
    detail_lower = exc_info.value.detail.lower()
    assert "permanently delete" not in detail_lower
    assert "delete" not in detail_lower

    # Conflict path must not have touched the archived copy either.
    assert db_session.query(PressureTest).filter(PressureTest.id == archived.id).count() == 1
    assert db_session.query(RevisionModel).filter(RevisionModel.id == revision.id).count() == 1
    assert db_session.query(Artifact).filter(Artifact.id == artifact.id).count() == 1
    assert artifact_file.exists()


def test_permanent_delete_is_admin_only_and_does_not_mutate(db_session, tmp_path, monkeypatch, foreman_user):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)

    test, revision, artifact, artifact_file = _archived_test_with_artifact(
        db_session, tmp_path, "PERM-DELETE-1", age_days=90
    )
    test_id, revision_id, artifact_id = test.id, revision.id, artifact.id

    with pytest.raises(HTTPException) as exc_info:
        permanently_delete_test(log_no="PERM-DELETE-1", current_user=foreman_user, db=db_session)

    assert exc_info.value.status_code == 403
    assert "administrator" in exc_info.value.detail.lower()

    # Nothing deleted: same rows, same file.
    assert db_session.query(PressureTest).filter(PressureTest.id == test_id).count() == 1
    assert db_session.query(RevisionModel).filter(RevisionModel.id == revision_id).count() == 1
    assert db_session.query(Artifact).filter(Artifact.id == artifact_id).count() == 1
    assert artifact_file.exists()


def test_admin_permanent_delete_removes_archived_log_files_and_shares(
    db_session, tmp_path, monkeypatch, admin_user
):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    test, revision, artifact, artifact_file = _archived_test_with_artifact(
        db_session, tmp_path, "PERM-DELETE-ADMIN-1", age_days=90
    )
    test_id, revision_id, artifact_id = test.id, revision.id, artifact.id
    db_session.add(PublicShare(pressure_test_id=test_id, created_by_user_id=admin_user.id))
    db_session.commit()

    permanently_delete_test(
        log_no="PERM-DELETE-ADMIN-1", current_user=admin_user, db=db_session
    )

    assert db_session.query(PressureTest).filter(PressureTest.id == test_id).count() == 0
    assert db_session.query(RevisionModel).filter(RevisionModel.id == revision_id).count() == 0
    assert db_session.query(Artifact).filter(Artifact.id == artifact_id).count() == 0
    assert db_session.query(PublicShare).filter(PublicShare.pressure_test_id == test_id).count() == 0
    assert not artifact_file.exists()

    event = db_session.query(AuditEvent).filter(
        AuditEvent.entity_type == "pressure_test",
        AuditEvent.entity_id == test_id,
    ).one()
    assert event.action == "test_permanently_deleted"
    assert event.details_json["artifact_count"] == 1
    assert event.details_json["share_count"] == 1


def test_permanent_delete_does_not_delete_active_log(db_session, tmp_path, monkeypatch, admin_user):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    test, revision, artifact, artifact_file = _active_test_with_artifact(
        db_session, tmp_path, "PERM-DELETE-ACTIVE-1"
    )

    with pytest.raises(HTTPException) as exc_info:
        permanently_delete_test(
            log_no="PERM-DELETE-ACTIVE-1", current_user=admin_user, db=db_session
        )

    assert exc_info.value.status_code == 404
    assert db_session.query(PressureTest).filter(PressureTest.id == test.id).count() == 1
    assert db_session.query(RevisionModel).filter(RevisionModel.id == revision.id).count() == 1
    assert db_session.query(Artifact).filter(Artifact.id == artifact.id).count() == 1
    assert artifact_file.exists()


def test_permanent_delete_still_404s_for_unknown_log(db_session, admin_user):
    with pytest.raises(HTTPException) as exc_info:
        permanently_delete_test(log_no="DOES-NOT-EXIST", current_user=admin_user, db=db_session)
    assert exc_info.value.status_code == 404


def _active_test_with_artifact(db_session, tmp_path, log_no, file_type="photo"):
    """Creates a non-archived PressureTest + TestRevision + Artifact backed by a real
    file - delete_artifact() only matches artifacts under non-archived tests."""
    test = PressureTest(log_no=log_no, is_archived=False)
    db_session.add(test)
    db_session.commit()

    revision = RevisionModel(
        pressure_test_id=test.id,
        revision_id="r1",
        status="complete",
        is_primary=True,
    )
    db_session.add(revision)
    db_session.commit()

    artifact_relpath = f"logs/{log_no}/revisions/r1/graph.png"
    artifact_file = tmp_path / artifact_relpath
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_bytes(b"regression-test placeholder png bytes")

    artifact = Artifact(
        test_revision_id=revision.id,
        name="graph.png",
        relative_path=artifact_relpath,
        file_type=file_type,
        size_bytes=artifact_file.stat().st_size,
        sha256="1" * 64,
        storage_key=artifact_relpath,
    )
    db_session.add(artifact)
    db_session.commit()

    return test, revision, artifact, artifact_file


def test_delete_photo_is_admin_only_and_does_not_mutate(db_session, tmp_path, monkeypatch, foreman_user):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)

    test, revision, artifact, artifact_file = _active_test_with_artifact(
        db_session, tmp_path, "ARTIFACT-DELETE-1"
    )
    artifact_id = artifact.id

    with pytest.raises(HTTPException) as exc_info:
        delete_artifact(artifact_id=artifact_id, current_user=foreman_user, db=db_session)

    assert exc_info.value.status_code == 403
    assert "administrator" in exc_info.value.detail.lower()

    # Nothing unlinked or deleted: same row, same file.
    assert db_session.query(Artifact).filter(Artifact.id == artifact_id).count() == 1
    assert artifact_file.exists()


def test_admin_can_delete_photo_and_audit_it(db_session, tmp_path, monkeypatch, admin_user):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    test, revision, artifact, artifact_file = _active_test_with_artifact(
        db_session, tmp_path, "ARTIFACT-DELETE-ADMIN-1"
    )
    artifact_id = artifact.id

    updated_test = delete_artifact(
        artifact_id=artifact_id, current_user=admin_user, db=db_session
    )

    assert updated_test.id == test.id
    assert db_session.query(Artifact).filter(Artifact.id == artifact_id).count() == 0
    assert not artifact_file.exists()
    event = db_session.query(AuditEvent).filter(
        AuditEvent.entity_type == "artifact",
        AuditEvent.entity_id == artifact_id,
    ).one()
    assert event.action == "photo_deleted"
    assert event.details_json["log_no"] == test.log_no


def test_admin_cannot_individually_delete_non_photo_artifacts(db_session, tmp_path, monkeypatch, admin_user):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    _, _, artifact, artifact_file = _active_test_with_artifact(
        db_session, tmp_path, "ARTIFACT-DELETE-GRAPH-1", file_type="graph_png"
    )

    with pytest.raises(HTTPException) as exc_info:
        delete_artifact(artifact_id=artifact.id, current_user=admin_user, db=db_session)

    assert exc_info.value.status_code == 400
    assert db_session.query(Artifact).filter(Artifact.id == artifact.id).count() == 1
    assert artifact_file.exists()


def test_delete_artifact_still_404s_for_unknown_id(db_session, admin_user):
    with pytest.raises(HTTPException) as exc_info:
        delete_artifact(artifact_id="00000000-0000-0000-0000-000000000000", current_user=admin_user, db=db_session)
    assert exc_info.value.status_code == 404


def _ptr_link(db, test, revision):
    record = PressureTestRecord(record_number="PTR-DELETE-GUARD", is_archived=True)
    db.add(record)
    db.flush()
    link = PressureTestRecordLog(
        record_id=record.id, pressure_test_id=test.id, test_revision_id=revision.id,
    )
    db.add(link)
    db.commit()
    return link


def test_archived_ptr_still_protects_log(db_session, tmp_path, monkeypatch, admin_user):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    test, revision, artifact, path = _archived_test_with_artifact(
        db_session, tmp_path, "PTR-LOG", 90,
    )
    link = _ptr_link(db_session, test, revision)
    with pytest.raises(HTTPException) as exc:
        permanently_delete_test(test.log_no, admin_user, db_session)
    assert exc.value.status_code == 409
    assert db_session.get(PressureTestRecordLog, link.id)
    assert db_session.get(Artifact, artifact.id)
    assert path.exists()
    assert db_session.query(AuditEvent).count() == 0


@pytest.mark.parametrize("by_key_only", [False, True])
@pytest.mark.parametrize("whole_log", [False, True])
def test_ptr_file_reference_protects_deletion(
    db_session, tmp_path, monkeypatch, admin_user, by_key_only, whole_log,
):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    test, revision, artifact, path = _active_test_with_artifact(
        db_session, tmp_path, "PTR-PHOTO",
    )
    other, other_revision, _, _ = _active_test_with_artifact(
        db_session, tmp_path, "PTR-OTHER",
    )
    link = _ptr_link(db_session, other, other_revision)
    db_session.add(PressureTestRecordLogArtifact(
        record_log_id=link.id, artifact_id=None if by_key_only else artifact.id,
        name=artifact.name, storage_key=artifact.storage_key, sha256=artifact.sha256,
        is_included_in_pdf=False,
    ))
    test.is_archived = whole_log
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        if whole_log:
            permanently_delete_test(test.log_no, admin_user, db_session)
        else:
            delete_artifact(artifact.id, admin_user, db_session)
    assert exc.value.status_code == 409
    assert path.exists()
    assert db_session.get(Artifact, artifact.id)


@pytest.mark.parametrize("whole_log", [False, True])
def test_shared_storage_key_protects_other_attachment(
    db_session, tmp_path, monkeypatch, admin_user, whole_log,
):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    test, revision, artifact, path = _active_test_with_artifact(
        db_session, tmp_path, "SHARED-PHOTO",
    )
    _, other_revision, other_artifact, _ = _active_test_with_artifact(
        db_session, tmp_path, "SHARED-OTHER",
    )
    other_artifact.storage_key = artifact.storage_key
    test.is_archived = whole_log
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        if whole_log:
            permanently_delete_test(test.log_no, admin_user, db_session)
        else:
            delete_artifact(artifact.id, admin_user, db_session)
    assert exc.value.status_code == 409
    assert path.exists()


@pytest.mark.parametrize("whole_log", [False, True])
def test_commit_failure_restores_file_and_database(
    db_session, tmp_path, monkeypatch, admin_user, whole_log,
):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    test, revision, artifact, path = _active_test_with_artifact(
        db_session, tmp_path, "ROLLBACK-PHOTO",
    )
    test.is_archived = whole_log
    share = PublicShare(pressure_test_id=test.id)
    db_session.add(share)
    db_session.commit()
    test_id, artifact_id, share_id = test.id, artifact.id, share.id
    original_bytes = path.read_bytes()

    def fail_commit():
        db_session.flush()  # Exercise rollback after SQL DELETEs have executed.
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated database failure"):
        if whole_log:
            permanently_delete_test(test.log_no, admin_user, db_session)
        else:
            delete_artifact(artifact.id, admin_user, db_session)
    assert db_session.get(PressureTest, test_id)
    assert db_session.get(Artifact, artifact_id)
    assert db_session.get(PublicShare, share_id)
    assert db_session.query(AuditEvent).count() == 0
    assert path.read_bytes() == original_bytes
    assert not list((tmp_path / ".deletions").iterdir())


def test_staging_failure_restores_previously_staged_files(
    db_session, tmp_path, monkeypatch, admin_user,
):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    test, revision, artifact, path = _archived_test_with_artifact(
        db_session, tmp_path, "STAGE-FAILURE", 90,
    )
    _, _, second, second_path = _active_test_with_artifact(
        db_session, tmp_path, "STAGE-SECOND",
    )
    second.test_revision_id = revision.id
    db_session.commit()
    real_stage = storage_module.storage.stage_file_deletion
    staged_calls = []

    def fail_second_stage(key):
        staged_calls.append(key)
        if len(staged_calls) == 2:
            raise OSError("simulated disk failure")
        return real_stage(key)

    monkeypatch.setattr(storage_module.storage, "stage_file_deletion", fail_second_stage)
    with pytest.raises(OSError, match="simulated disk failure"):
        permanently_delete_test(test.log_no, admin_user, db_session)
    assert path.exists() and second_path.exists()
    assert db_session.query(Artifact).count() == 2
    assert db_session.query(AuditEvent).count() == 0


def test_cleanup_failure_keeps_audited_recovery_keys(
    db_session, tmp_path, monkeypatch, admin_user,
):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    test, revision, artifact, path = _active_test_with_artifact(
        db_session, tmp_path, "CLEANUP-FAILURE",
    )
    artifact_id = artifact.id

    def fail_cleanup(staged):
        raise PermissionError("simulated unlink failure")

    monkeypatch.setattr(storage_module.storage, "finalize_file_deletion", fail_cleanup)
    with pytest.raises(HTTPException) as exc:
        delete_artifact(artifact.id, admin_user, db_session)
    assert exc.value.status_code == 500
    assert "was deleted" in exc.value.detail
    assert db_session.get(Artifact, artifact_id) is None
    assert not path.exists()
    event = db_session.query(AuditEvent).one()
    staged = event.details_json["files"][0]
    assert staged["original_key"] == str(path.relative_to(tmp_path))
    assert (tmp_path / staged["staged_key"]).exists()
    assert (tmp_path / staged["staged_key"]).with_suffix(".json").exists()


def test_permanent_delete_selects_archived_identity_not_reused_name(
    db_session, tmp_path, monkeypatch, admin_user,
):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    first = PressureTest(log_no="REUSED", is_archived=True)
    second = PressureTest(log_no="REUSED", is_archived=True)
    active = PressureTest(log_no="REUSED", is_archived=False)
    db_session.add_all([first, second, active])
    db_session.commit()
    first_id, second_id, active_id = first.id, second.id, active.id
    with pytest.raises(HTTPException) as exc:
        permanently_delete_test("REUSED", admin_user, db_session)
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException) as exc:
        permanently_delete_test("REUSED", admin_user, db_session, test_id=active_id)
    assert exc.value.status_code == 404
    permanently_delete_test("REUSED", admin_user, db_session, test_id=second_id)
    assert db_session.get(PressureTest, first_id)
    assert db_session.get(PressureTest, active_id)
    assert db_session.get(PressureTest, second_id) is None


def test_permanent_delete_cascades_all_revisions_and_preserves_old_audit(
    db_session, tmp_path, monkeypatch, admin_user,
):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    test, first, artifact, path = _archived_test_with_artifact(
        db_session, tmp_path, "ALL-REVISIONS", 90,
    )
    second = RevisionModel(pressure_test_id=test.id, revision_id="r2", status="archived")
    db_session.add(second)
    db_session.flush()
    db_session.add_all([
        Pipe(test_revision_id=first.id, pipe_number="1/1"),
        Bundle(test_revision_id=second.id, bundle_number="1"),
        Artifact(test_revision_id=second.id, name=artifact.name, relative_path=artifact.relative_path,
                 file_type=artifact.file_type, size_bytes=artifact.size_bytes,
                 sha256=artifact.sha256, storage_key=artifact.storage_key),
        AuditEvent(entity_type="pressure_test", entity_id=test.id, action="test_deleted"),
    ])
    db_session.commit()
    permanently_delete_test(test.log_no, admin_user, db_session)
    for model in (PressureTest, RevisionModel, Artifact, Pipe, Bundle):
        assert db_session.query(model).count() == 0
    assert {event.action for event in db_session.query(AuditEvent)} == {
        "test_deleted", "test_permanently_deleted",
    }
    assert not path.exists()


@pytest.mark.parametrize("whole_log", [False, True])
def test_missing_storage_file_does_not_block_deletion(
    db_session, tmp_path, monkeypatch, admin_user, whole_log,
):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)
    test, revision, artifact, path = _active_test_with_artifact(
        db_session, tmp_path, "MISSING-FILE",
    )
    test.is_archived = whole_log
    db_session.commit()
    artifact_id = artifact.id
    path.unlink()
    if whole_log:
        permanently_delete_test(test.log_no, admin_user, db_session)
    else:
        delete_artifact(artifact.id, admin_user, db_session)
    assert db_session.get(Artifact, artifact_id) is None
    assert db_session.query(AuditEvent).count() == 1


@pytest.fixture()
def api_client(db_session, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from services.api.database import get_db
    from services.api.main import app

    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)

    def isolated_db():
        yield db_session

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = isolated_db
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def _login(client, username):
    from services.api.config import settings

    response = client.post("/api/v1/auth/login", json={
        "username": username, "password": "irrelevant",
    }, headers={"Origin": settings.public_origin, "X-Ardor-Session-Mode": "browser"})
    assert response.status_code == 200, response.text
    return {"Origin": settings.public_origin,
            "X-CSRF-Token": client.cookies[settings.csrf_cookie_name]}


def test_browser_session_photo_archive_permanent_delete_flow(
    api_client, db_session, tmp_path, admin_user,
):
    test, revision, photo, photo_path = _active_test_with_artifact(
        db_session, tmp_path, "API-DELETE",
    )
    test_id, photo_id = test.id, photo.id
    headers = _login(api_client, admin_user.username)
    # A real cookie session still needs CSRF protection for destructive operations.
    assert api_client.delete(f"/api/v1/tests/artifacts/{photo_id}").status_code == 403
    assert photo_path.exists()
    response = api_client.delete(f"/api/v1/tests/artifacts/{photo_id}", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["revisions"][0]["artifacts"] == []
    assert not photo_path.exists()
    assert api_client.get(f"/api/v1/tests/artifacts/{photo_id}/file").status_code == 404
    share_response = api_client.post("/api/v1/shares", json={"log_no": test.log_no}, headers=headers)
    assert share_response.status_code == 200, share_response.text
    response = api_client.delete(f"/api/v1/tests/{test.log_no}", headers=headers)
    assert response.status_code == 200, response.text
    assert [row["id"] for row in api_client.get("/api/v1/tests/trash").json()] == [test_id]
    response = api_client.delete(
        f"/api/v1/tests/{test.log_no}/permanent", params={"test_id": test_id}, headers=headers,
    )
    assert response.status_code == 200, response.text
    assert api_client.get("/api/v1/tests/trash").json() == []
    assert db_session.query(PressureTest).count() == 0
    assert db_session.query(PublicShare).count() == 0
    assert {row.action for row in db_session.query(AuditEvent)} >= {
        "photo_deleted", "test_deleted", "test_permanently_deleted",
    }


@pytest.mark.parametrize("role", ["anonymous", "foreman", "viewer"])
def test_api_rejects_deletion_without_admin_role(api_client, db_session, tmp_path, role):
    test, revision, photo, path = _active_test_with_artifact(
        db_session, tmp_path, "API-ROLE",
    )
    archived = PressureTest(log_no="API-ARCHIVED", is_archived=True)
    db_session.add(archived)
    headers = {}
    if role != "anonymous":
        user = User(username=f"role-{role}", hashed_password=hash_password("irrelevant"),
                    role=role, is_active=True)
        db_session.add(user)
        db_session.commit()
        headers = _login(api_client, user.username)
    else:
        db_session.commit()
    photo_response = api_client.delete(f"/api/v1/tests/artifacts/{photo.id}", headers=headers)
    log_response = api_client.delete(
        f"/api/v1/tests/{archived.log_no}/permanent", headers=headers,
    )
    expected_status = 401 if role == "anonymous" else 403
    assert photo_response.status_code == expected_status
    assert log_response.status_code == expected_status
    assert db_session.get(Artifact, photo.id)
    assert db_session.get(PressureTest, archived.id)
    assert path.exists()
