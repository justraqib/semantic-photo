from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_current_user
from app.core.database import get_db
from app.models.memory import Memory
from app.models.photo import Photo
from app.models.user import User
from app.services.storage import generate_presigned_url

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("")
async def get_today_memory(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    result = await db.execute(
        select(Memory)
        .where(Memory.user_id == current_user.id, Memory.memory_date == today)
        .order_by(desc(Memory.created_at))
        .limit(1)
    )
    memory = result.scalar_one_or_none()
    if memory is None:
        return None

    memory_photo_ids: list[UUID] = []
    for raw_id in memory.photo_ids:
        try:
            memory_photo_ids.append(UUID(str(raw_id)))
        except ValueError:
            continue

    photos_result = await db.execute(
        select(Photo.id, Photo.thumbnail_key)
        .where(
            Photo.id.in_(memory_photo_ids),
            Photo.user_id == current_user.id,
            Photo.is_deleted.is_(False),
        )
    )
    photo_rows = photos_result.all()
    thumb_by_id = {str(photo_id): thumbnail_key for photo_id, thumbnail_key in photo_rows}

    photos = []
    for raw_id in memory.photo_ids:
        photo_id = str(raw_id)
        thumbnail_key = thumb_by_id.get(photo_id)
        if not thumbnail_key:
            continue
        photos.append(
            {
                "id": photo_id,
                "thumbnail_url": generate_presigned_url(thumbnail_key),
            }
        )

    return {
        "id": str(memory.id),
        "label": memory.label,
        "memory_date": memory.memory_date.isoformat(),
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
        "photo_ids": [str(pid) for pid in memory.photo_ids],
        "photos": photos,
        "photo_count": len(photos),
    }
