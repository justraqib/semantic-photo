import uuid

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Album(Base):
    __tablename__ = "albums"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class AlbumPhoto(Base):
    __tablename__ = "album_photos"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
