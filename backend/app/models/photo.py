import uuid

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Photo(Base):
    __tablename__ = "photos"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
