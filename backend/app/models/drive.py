from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Text
from sqlalchemy import Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class DriveSyncState(Base):
    __tablename__ = "drive_sync_state"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    folder_id = Column(Text, nullable=True)
    folder_name = Column(Text, nullable=True)
    next_page_token = Column(Text, nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    sync_enabled = Column(Boolean, nullable=False, server_default="true")
    last_error = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default="idle")
    pending_count = Column(Integer, nullable=False, server_default="0")
    processed_count = Column(Integer, nullable=False, server_default="0")
    imported_count = Column(Integer, nullable=False, server_default="0")
    skipped_count = Column(Integer, nullable=False, server_default="0")
    failed_count = Column(Integer, nullable=False, server_default="0")
