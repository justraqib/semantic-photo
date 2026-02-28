import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class DriveSyncJob(Base):
    __tablename__ = "drive_sync_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    folder_id = Column(Text, nullable=False)
    status = Column(String, nullable=False, server_default="queued")
    job_type = Column(String, nullable=False, server_default="full_sync")
    attempts = Column(Integer, nullable=False, server_default="0")
    max_attempts = Column(Integer, nullable=False, server_default="5")
    batch_size = Column(Integer, nullable=False, server_default="50")
    last_error = Column(Text, nullable=True)
    total_discovered = Column(Integer, nullable=False, server_default="0")
    processed_count = Column(Integer, nullable=False, server_default="0")
    uploaded_count = Column(Integer, nullable=False, server_default="0")
    skipped_count = Column(Integer, nullable=False, server_default="0")
    failed_count = Column(Integer, nullable=False, server_default="0")
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class DriveSyncFile(Base):
    __tablename__ = "drive_sync_files"
    __table_args__ = (
        UniqueConstraint("user_id", "source_file_id", "source_entry_id", name="uq_drive_sync_file_source"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("drive_sync_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_file_id = Column(Text, nullable=False)
    source_entry_id = Column(Text, nullable=True)
    filename = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    state = Column(String, nullable=False, server_default="pending")
    batch_no = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DriveSyncCheckpoint(Base):
    __tablename__ = "drive_sync_checkpoints"

    job_id = Column(UUID(as_uuid=True), ForeignKey("drive_sync_jobs.id", ondelete="CASCADE"), primary_key=True)
    last_batch_no = Column(Integer, nullable=False, server_default="0")
    last_success_key = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
