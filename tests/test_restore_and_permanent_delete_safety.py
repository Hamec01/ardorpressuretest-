"""R1b regression guard:
- restore_test() must restore an old archived log (no age-based purge/410 Gone) as
  long as there is no active Log No. conflict, and its conflict message must not
  suggest permanent deletion (that path is disabled).
- permanently_delete_test() must always refuse (never delete DB rows or files),
  regardless of role or age.
- delete_artifact() must always refuse (never unlink the file or delete the row).

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
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.database import Base
from services.api.models import Artifact, PressureTest, TestRevision as RevisionModel, User
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


def test_permanent_delete_is_disabled_and_does_not_mutate(db_session, tmp_path, monkeypatch, foreman_user):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)

    test, revision, artifact, artifact_file = _archived_test_with_artifact(
        db_session, tmp_path, "PERM-DELETE-1", age_days=90
    )
    test_id, revision_id, artifact_id = test.id, revision.id, artifact.id

    with pytest.raises(HTTPException) as exc_info:
        permanently_delete_test(log_no="PERM-DELETE-1", current_user=foreman_user, db=db_session)

    assert exc_info.value.status_code == 403
    assert "disabled" in exc_info.value.detail.lower()

    # Nothing deleted: same rows, same file.
    assert db_session.query(PressureTest).filter(PressureTest.id == test_id).count() == 1
    assert db_session.query(RevisionModel).filter(RevisionModel.id == revision_id).count() == 1
    assert db_session.query(Artifact).filter(Artifact.id == artifact_id).count() == 1
    assert artifact_file.exists()


def test_permanent_delete_still_404s_for_unknown_log(db_session, foreman_user):
    with pytest.raises(HTTPException) as exc_info:
        permanently_delete_test(log_no="DOES-NOT-EXIST", current_user=foreman_user, db=db_session)
    assert exc_info.value.status_code == 404


def _active_test_with_artifact(db_session, tmp_path, log_no):
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
        file_type="graph_png",
        size_bytes=artifact_file.stat().st_size,
        sha256="1" * 64,
        storage_key=artifact_relpath,
    )
    db_session.add(artifact)
    db_session.commit()

    return test, revision, artifact, artifact_file


def test_delete_artifact_is_disabled_and_does_not_mutate(db_session, tmp_path, monkeypatch, foreman_user):
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)

    test, revision, artifact, artifact_file = _active_test_with_artifact(
        db_session, tmp_path, "ARTIFACT-DELETE-1"
    )
    artifact_id = artifact.id

    with pytest.raises(HTTPException) as exc_info:
        delete_artifact(artifact_id=artifact_id, current_user=foreman_user, db=db_session)

    assert exc_info.value.status_code == 403
    assert "disabled" in exc_info.value.detail.lower()

    # Nothing unlinked or deleted: same row, same file.
    assert db_session.query(Artifact).filter(Artifact.id == artifact_id).count() == 1
    assert artifact_file.exists()


def test_delete_artifact_still_404s_for_unknown_id(db_session, foreman_user):
    with pytest.raises(HTTPException) as exc_info:
        delete_artifact(artifact_id="00000000-0000-0000-0000-000000000000", current_user=foreman_user, db=db_session)
    assert exc_info.value.status_code == 404
