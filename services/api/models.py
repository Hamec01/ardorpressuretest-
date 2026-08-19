import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship
from services.api.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(128), nullable=True)
    role = Column(String(32), default="operator", nullable=False)  # operator, foreman, manager, admin
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class PressureTest(Base):
    __tablename__ = "pressure_tests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    log_no = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    revisions = relationship("TestRevision", back_populates="pressure_test", cascade="all, delete-orphan")


class TestRevision(Base):
    __tablename__ = "test_revisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pressure_test_id = Column(String(36), ForeignKey("pressure_tests.id"), nullable=False, index=True)
    revision_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default="complete", nullable=False)  # draft, complete, confirmed, archived
    is_primary = Column(Boolean, default=True, nullable=False)
    
    operator = Column(String(128), default="", nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False)
    metrics_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    pressure_test = relationship("PressureTest", back_populates="revisions")
    artifacts = relationship("Artifact", back_populates="revision", cascade="all, delete-orphan")
    pipes = relationship("Pipe", back_populates="revision", cascade="all, delete-orphan")
    bundles = relationship("Bundle", back_populates="revision", cascade="all, delete-orphan")


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    test_revision_id = Column(String(36), ForeignKey("test_revisions.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    relative_path = Column(String(512), nullable=False)
    file_type = Column(String(32), nullable=False)  # source_csv, graph_png, excel_xlsx, text_txt, report_pdf, photo
    category = Column(String(32), nullable=True)  # pipe, gauge, installation, other
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    storage_key = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    revision = relationship("TestRevision", back_populates="artifacts")


class Pipe(Base):
    __tablename__ = "pipes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    test_revision_id = Column(String(36), ForeignKey("test_revisions.id"), nullable=False, index=True)
    pipe_number = Column(String(128), nullable=False, index=True)

    revision = relationship("TestRevision", back_populates="pipes")


class Bundle(Base):
    __tablename__ = "bundles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    test_revision_id = Column(String(36), ForeignKey("test_revisions.id"), nullable=False, index=True)
    bundle_number = Column(String(128), nullable=False, index=True)

    revision = relationship("TestRevision", back_populates="bundles")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=True)
    actor_name = Column(String(128), nullable=True)
    action = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False)
    details_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
