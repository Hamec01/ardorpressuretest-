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
    
    # PipeCloud workflow manual status
    pipecloud_added = Column(Boolean, default=False, nullable=False)
    pipecloud_updated_at = Column(DateTime(timezone=True), nullable=True)
    pipecloud_updated_by_user_id = Column(String(36), nullable=True)
    pipecloud_updated_by_name = Column(String(128), nullable=True)

    is_archived = Column(Boolean, default=False, nullable=False)
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


class PressureTestRecord(Base):
    __tablename__ = "pressure_test_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    record_number = Column(String(64), unique=True, index=True, nullable=False)
    project = Column(String(128), nullable=False, default="ARDOR Project")
    system = Column(String(128), nullable=False, default="Piping System")
    ins_no = Column(String(64), nullable=True)
    test_date = Column(String(32), nullable=True)
    test_medium = Column(String(64), default="Water")
    design_pressure = Column(String(64), nullable=True)
    test_pressure = Column(String(64), nullable=True)
    duration_min = Column(String(32), default="60 min")
    status = Column(String(32), default="draft", nullable=False)  # draft, complete, confirmed, signed
    foreman_name = Column(String(128), nullable=True)
    qc_inspector = Column(String(128), nullable=True)
    client_surveyor = Column(String(128), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Электронная верификация и подписи
    verification_code = Column(String(64), unique=True, index=True, nullable=True)
    confirmed_by_user_id = Column(String(36), nullable=True)
    confirmed_by_name = Column(String(128), nullable=True)
    confirmed_by_role = Column(String(64), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    signature_image_path = Column(String(255), nullable=True)
    signed_copy_path = Column(String(255), nullable=True)
    sha256_hash = Column(String(64), nullable=True)

    # Actual PDF SHA-256 digests and metadata snapshot
    official_pdf_sha256 = Column(String(64), nullable=True)
    full_pdf_sha256 = Column(String(64), nullable=True)
    snapshot_json = Column(JSON, default=dict, nullable=False)

    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    items = relationship("PressureTestRecordItem", back_populates="record", cascade="all, delete-orphan")
    logs = relationship("PressureTestRecordLog", back_populates="record", cascade="all, delete-orphan", order_by="PressureTestRecordLog.position")


class PressureTestRecordLog(Base):
    __tablename__ = "pressure_test_record_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    record_id = Column(String(36), ForeignKey("pressure_test_records.id"), nullable=False, index=True)
    pressure_test_id = Column(String(36), ForeignKey("pressure_tests.id"), nullable=False, index=True)
    test_revision_id = Column(String(36), ForeignKey("test_revisions.id"), nullable=False, index=True)
    position = Column(Integer, default=0, nullable=False)
    include_measurement_table = Column(Boolean, default=True, nullable=False)
    selected_pipe_numbers = Column(JSON, default=list, nullable=False)
    metadata_snapshot = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    record = relationship("PressureTestRecord", back_populates="logs")
    pressure_test = relationship("PressureTest")
    revision = relationship("TestRevision")
    artifacts = relationship("PressureTestRecordLogArtifact", back_populates="record_log", cascade="all, delete-orphan", order_by="PressureTestRecordLogArtifact.position")
    items = relationship("PressureTestRecordItem", back_populates="record_log")


class PressureTestRecordLogArtifact(Base):
    __tablename__ = "pressure_test_record_log_artifacts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    record_log_id = Column(String(36), ForeignKey("pressure_test_record_logs.id"), nullable=False, index=True)
    artifact_id = Column(String(36), ForeignKey("artifacts.id"), nullable=True, index=True)
    source = Column(String(32), default="log_artifact", nullable=False)  # log_artifact, ptr_upload, generated_from_csv
    category = Column(String(32), default="other", nullable=False)  # graph, gauge, pipe, installation, measurement_table, other
    name = Column(String(255), nullable=False)
    storage_key = Column(String(512), nullable=False)
    sha256 = Column(String(64), nullable=False)
    position = Column(Integer, default=0, nullable=False)
    is_included_in_pdf = Column(Boolean, default=True, nullable=False)
    created_by_name = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    record_log = relationship("PressureTestRecordLog", back_populates="artifacts")
    source_artifact = relationship("Artifact")


class PressureTestRecordItem(Base):
    __tablename__ = "pressure_test_record_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    record_id = Column(String(36), ForeignKey("pressure_test_records.id"), nullable=False, index=True)
    record_log_id = Column(String(36), ForeignKey("pressure_test_record_logs.id"), nullable=True, index=True)
    item_no = Column(Integer, nullable=False)
    pipe_number = Column(String(128), nullable=False)
    drawing_no = Column(String(128), nullable=True)
    spool_no = Column(String(128), nullable=True)
    log_no = Column(String(64), nullable=True)
    hold_start_bar = Column(String(32), nullable=True)
    hold_end_bar = Column(String(32), nullable=True)
    result = Column(String(32), default="PASS", nullable=False)  # PASS, FAIL, PENDING
    notes = Column(String(255), nullable=True)

    record = relationship("PressureTestRecord", back_populates="items")
    record_log = relationship("PressureTestRecordLog", back_populates="items")
