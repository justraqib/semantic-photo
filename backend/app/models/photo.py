import uuid

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class Photo(Base):
    __tablename__ = "photos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    storage_key = Column(String, nullable=False)
    thumbnail_key = Column(String, nullable=True)
    original_filename = Column(String, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    mime_type = Column(String, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    taken_at = Column(DateTime(timezone=True), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source = Column(String, nullable=True)
    source_id = Column(String, nullable=True)
    phash = Column(String, nullable=True)
    embedding = Column(Vector(512), nullable=True)
    embedding_generated_at = Column(DateTime(timezone=True), nullable=True)
    caption = Column(Text, nullable=True)
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    camera_make = Column(String, nullable=True)
    is_deleted = Column(Boolean, server_default="false", nullable=False)

    user = relationship("User", back_populates="photos")
