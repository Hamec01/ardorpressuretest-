import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, JSON, UniqueConstraint, text
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
    role = Column(String(32), default="viewer", nullable=False)  # admin, foreman, viewer (ADR-005); legacy rows may still read "operator"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    # R3b: additive only - no auth code reads or writes this yet. Forces a password
    # change on next login once R3's change-password flow exists; true only ever set by
    # an admin-driven create/reset action (also not implemented yet).
    must_change_password = Column(Boolean, default=False, nullable=False)


class PasswordLink(Base):
    """One-time link that lets an account holder set a new password without the old one.

    Created by an admin for a new account ("invite") or a lost password ("reset");
    see docs/ACCESS_PLAN_R4-R7.md stage 1. Only the SHA-256 digest of the 256-bit
    token is stored, never the token itself. A link is usable only while it is unused,
    unrevoked, unexpired and its account is active.
    """
    __tablename__ = "password_links"
    __table_args__ = (
        CheckConstraint("purpose IN ('invite', 'reset')", name="ck_password_links_purpose"),
        CheckConstraint("length(token_hash) = 64", name="ck_password_links_token_hash_length"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)
    purpose = Column(String(16), nullable=False)
    created_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class PublicShare(Base):
    """Public read-only link to one pressure test log (ADR-005 §10, docs/ACCESS_PLAN_R4-R7.md stage 2).

    The link token is derived as HMAC(ARDOR_SHARE_SECRET, id) and is never stored.
    legacy_log_no_access marks the compatibility record that keeps an old
    /share/{log_no} URL working for a log that existed before token links.
    Revocation is logical (revoked_at); rows are never deleted.
    """
    __tablename__ = "public_shares"
    __table_args__ = (
        CheckConstraint("resource_type IN ('log')", name="ck_public_shares_resource_type"),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_user_id IS NULL) OR revoked_at IS NOT NULL",
            name="ck_public_shares_revoked_by_requires_revoked_at",
        ),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    resource_type = Column(String(16), default="log", nullable=False)
    pressure_test_id = Column(String(36), ForeignKey("pressure_tests.id"), index=True, nullable=False)
    legacy_log_no_access = Column(Boolean, default=False, nullable=False)
    created_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    access_count = Column(Integer, default=0, nullable=False)


class Gauge(Base):
    __tablename__ = "gauges"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    serial_number = Column(String(128), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class PressureTest(Base):
    __tablename__ = "pressure_tests"
    __table_args__ = (
        Index(
            "uq_pressure_tests_active_log_no",
            "log_no",
            unique=True,
            postgresql_where=text("is_archived = false"),
        ),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    # No plain index=True here: the canonical index on log_no is the existing partial
    # unique index below (uq_pressure_tests_active_log_no) - a second, redundant plain
    # btree index was never actually created by any migration and does not exist on
    # live either, so the model must not claim one.
    log_no = Column(String(64), nullable=False)

    # PipeCloud workflow manual status
    pipecloud_added = Column(Boolean, default=False, nullable=False)
    pipecloud_updated_at = Column(DateTime(timezone=True), nullable=True)
    pipecloud_updated_by_user_id = Column(String(36), nullable=True)
    pipecloud_updated_by_name = Column(String(128), nullable=True)

    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # R2a: additive actor references, independent of the legacy pipecloud_updated_by_*
    # fields above and of audit_events - none of those are rewritten by this addition.
    created_by_user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    updated_by_user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    responsible_user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)  # current responsible person, distinct from authorship and from any access right

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

    # R2a: gauge selection. In Draft, gauge_id and gauge_serial_snapshot are updated
    # together whenever the selected Gauge changes. On transition to Complete,
    # gauge_serial_snapshot is fixed from the then-selected Gauge and becomes immutable;
    # any further change requires a new revision, not an edit of this one.
    gauge_id = Column(String(36), ForeignKey("gauges.id"), index=True, nullable=True)
    gauge_serial_snapshot = Column(String(128), nullable=True)
    created_by_user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    updated_by_user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)

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


class PlannedTestList(Base):
    __tablename__ = "planned_test_lists"
    __table_args__ = (
        CheckConstraint("priority >= 0 AND priority <= 3", name="ck_planned_test_lists_priority"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=0, nullable=False, index=True)
    # index=True reflects the existing ix_planned_test_lists_is_archived index, which a
    # migration already created on both a fresh chain and live - the model was simply
    # never updated to declare it.
    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    created_by_user_id = Column(String(36), nullable=True)  # legacy field, not touched by R2a - no FK, kept exactly as-is
    created_by_name = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # R2a: additive actor references. created_by_user_id above is untouched.
    updated_by_user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    responsible_user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)  # current responsible person, distinct from authorship and from any access right

    pipes = relationship("PlannedTestPipe", back_populates="planned_list", cascade="all, delete-orphan")


class PlannedTestPipe(Base):
    __tablename__ = "planned_test_pipes"
    __table_args__ = (
        UniqueConstraint("planned_test_list_id", "pipe_number", name="uq_planned_test_pipes_list_pipe"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    planned_test_list_id = Column(String(36), ForeignKey("planned_test_lists.id", ondelete="CASCADE"), nullable=False, index=True)
    pipe_number = Column(String(128), nullable=False, index=True)
    bundle_number = Column(String(128), nullable=False, index=True)
    pipe_sort_key = Column(String(128), nullable=False)
    source_data = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    planned_list = relationship("PlannedTestList", back_populates="pipes")


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
    custom_fields = Column(JSON, default=list, nullable=False)
    
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

    # R2a: additive actor references, independent of confirmed_by_* above (an electronic
    # signature/verification concept, not authorship or current responsibility).
    created_by_user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    updated_by_user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    responsible_user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)  # current responsible person, distinct from authorship and from any access right

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


class UserSession(Base):
    """R3b: additive schema only - no auth code creates, reads, revokes, or otherwise
    touches this table yet. See docs/adr/ADR-005-auth-session-model.md §8/§9 and the R3
    design correspondence for the session model this table implements; that behavior
    lands in a later R3b/R3 stage, not here.

    token_hash / previous_token_hash / csrf_token_hash store only a SHA-256 hex digest
    of a >=256-bit random secret - never the secret itself - matching the same
    hash-only discipline ADR-005 §10 already established for share tokens.
    previous_token_hash exists only for the desktop refresh-rotation reuse-detection
    design (R3 point 2); csrf_token_hash exists only for the browser cookie-CSRF design
    (R3 point 5) - the CHECK constraints below enforce which channel each applies to.
    """
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("channel IN ('browser', 'desktop')", name="ck_sessions_channel"),
        CheckConstraint(
            "(channel = 'browser' AND csrf_token_hash IS NOT NULL) OR "
            "(channel = 'desktop' AND csrf_token_hash IS NULL)",
            name="ck_sessions_csrf_token_hash_by_channel",
        ),
        CheckConstraint(
            "previous_token_hash IS NULL OR channel = 'desktop'",
            name="ck_sessions_previous_token_hash_desktop_only",
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_reason IS NOT NULL)",
            name="ck_sessions_revoked_at_reason_together",
        ),
        CheckConstraint("length(token_hash) = 64", name="ck_sessions_token_hash_length"),
        CheckConstraint(
            "previous_token_hash IS NULL OR length(previous_token_hash) = 64",
            name="ck_sessions_previous_token_hash_length",
        ),
        CheckConstraint(
            "csrf_token_hash IS NULL OR length(csrf_token_hash) = 64",
            name="ck_sessions_csrf_token_hash_length",
        ),
        CheckConstraint("expires_at > created_at", name="ck_sessions_expires_after_created"),
        Index(
            "ix_sessions_previous_token_hash",
            "previous_token_hash",
            postgresql_where=text("previous_token_hash IS NOT NULL"),
        ),
        Index(
            "ix_sessions_user_id_active",
            "user_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    # No ondelete="CASCADE": a user row referenced by a session is never silently
    # deletable out from under it - matches every other users.id FK in this file
    # (created_by_user_id/updated_by_user_id/responsible_user_id all default to the
    # same no-action behavior).
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    channel = Column(String(16), nullable=False)  # 'browser' | 'desktop'
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    previous_token_hash = Column(String(64), nullable=True)
    csrf_token_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_reason = Column(String(32), nullable=True)
    device_label = Column(String(128), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(256), nullable=True)
