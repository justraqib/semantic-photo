import uuid

from sqlalchemy import Column, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False, unique=True)

    photo_tags = relationship("PhotoTag", back_populates="tag", cascade="all, delete-orphan")


class PhotoTag(Base):
    __tablename__ = "photo_tags"

    photo_id = Column(UUID(as_uuid=True), ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    confidence = Column(Float, nullable=True)
    source = Column(Text, nullable=False, default="clip")

    photo = relationship("Photo", back_populates="photo_tags")
    tag = relationship("Tag", back_populates="photo_tags")
