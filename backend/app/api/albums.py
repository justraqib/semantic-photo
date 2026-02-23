from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_current_user
from app.core.database import get_db
from app.models.album import Album, AlbumPhoto
from app.models.photo import Photo
from app.models.user import User
from app.services.storage import generate_presigned_url

router = APIRouter(prefix="/albums", tags=["albums"])


@router.get("")
async def list_albums(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    photo_count_subquery = (
        select(AlbumPhoto.album_id, func.count().label("photo_count"))
        .group_by(AlbumPhoto.album_id)
        .subquery()
    )

    query = (
        select(
            Album.id,
            Album.name,
            Album.cover_photo_id,
            Photo.thumbnail_key.label("cover_thumbnail_key"),
            func.coalesce(photo_count_subquery.c.photo_count, 0).label("photo_count"),
        )
        .outerjoin(photo_count_subquery, photo_count_subquery.c.album_id == Album.id)
        .outerjoin(Photo, Photo.id == Album.cover_photo_id)
        .where(Album.user_id == current_user.id)
        .order_by(Album.created_at.desc())
    )
    result = await db.execute(query)
    rows = result.mappings().all()

    albums = []
    for row in rows:
        cover_thumbnail_url = (
            generate_presigned_url(row["cover_thumbnail_key"])
            if row["cover_thumbnail_key"]
            else None
        )
        albums.append(
            {
                "id": str(row["id"]),
                "name": row["name"],
                "cover_photo_id": str(row["cover_photo_id"]) if row["cover_photo_id"] else None,
                "photo_count": int(row["photo_count"] or 0),
                "cover_thumbnail_url": cover_thumbnail_url,
            }
        )

    return albums
