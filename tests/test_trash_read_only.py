"""Regression guard for R1a: GET /api/v1/tests/trash must never mutate data.

Isolated by design:
- Does not import or reuse fixtures from test_auth_audit.py or any other existing test file.
- Actual test data lives in a private in-memory SQLite engine created inside this file,
  never the process-wide services.api.database engine/session.
- The storage singleton's base_path is monkeypatched to pytest's own tmp_path for the
  duration of the test, so no file ever touches a real storage directory.
- DATABASE_URL / STORAGE_DIR must be exported to isolated temporary values by the caller
  before pytest starts, because services.api.config.Settings() (and the storage.py module
  level singleton) read them at first import time - before any fixture can run. This file
  refuses to run if those look like a staging target.

Run with:
    DATABASE_URL=sqlite:////tmp/.../throwaway.db STORAGE_DIR=/tmp/.../throwaway_storage \
        pytest -q tests/test_trash_read_only.py
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

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from services.api.database import Base
from services.api.models import Artifact, PressureTest, TestRevision as TestRevisionModel
from services.api.routes.tests import list_trash
from services.api import storage as storage_module


@pytest.fixture()
def db_session():
    """A private, isolated in-memory SQLite database - never the app-wide engine/session."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_list_trash_returns_without_mutating_anything(db_session, tmp_path, monkeypatch):
    # Redirect the storage singleton's base_path to pytest's own tmp_path for this test only,
    # regardless of what STORAGE_DIR resolved to at process start.
    monkeypatch.setattr(storage_module.storage, "base_path", tmp_path)

    # Arrange: an archived PressureTest older than the 14-day retention window used by
    # purge_expired_trash(), plus one revision and one artifact backed by a real file.
    old_timestamp = datetime.now(timezone.utc) - timedelta(days=20)

    test = PressureTest(log_no="TRASH-RO-1", is_archived=True)
    db_session.add(test)
    db_session.commit()
    db_session.query(PressureTest).filter(PressureTest.id == test.id).update(
        {"updated_at": old_timestamp}
    )
    db_session.commit()

    revision = TestRevisionModel(
        pressure_test_id=test.id,
        revision_id="r1",
        status="complete",
        is_primary=True,
    )
    db_session.add(revision)
    db_session.commit()

    artifact_relpath = "logs/TRASH-RO-1/revisions/r1/report.pdf"
    artifact_file = tmp_path / artifact_relpath
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_bytes(b"regression-test placeholder bytes, not a real report")

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

    test_id, revision_id, artifact_id = test.id, revision.id, artifact.id

    # Sanity: this fixture is genuinely eligible for purge_expired_trash() today (archived +
    # older than 14 days) - if list_trash() ever calls it again, this test must fail. Compared
    # against the timestamp we set directly, not a value re-read through the ORM: SQLite has no
    # native timezone-aware DATETIME type, so an attribute re-fetched after commit() comes back
    # offset-naive and cannot be compared against an aware datetime.
    assert old_timestamp < datetime.now(timezone.utc) - timedelta(days=14)

    # Act: call the handler function directly - no HTTP, no ASGI app, no auth dependency
    # is exercised here since the route itself has none today.
    result = list_trash(db=db_session)

    # Assert: the archived record is returned.
    returned_ids = {t.id for t in result}
    assert test_id in returned_ids

    # Assert: nothing was purged - no delete side effects on any of the three rows.
    assert db_session.query(PressureTest).filter(PressureTest.id == test_id).count() == 1
    assert db_session.query(TestRevisionModel).filter(TestRevisionModel.id == revision_id).count() == 1
    assert db_session.query(Artifact).filter(Artifact.id == artifact_id).count() == 1

    # Assert: the artifact file was not unlinked from disk.
    assert artifact_file.exists()
