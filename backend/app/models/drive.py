from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Text
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
