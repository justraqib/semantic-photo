from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_current_user
from app.core.database import get_db
from app.models.album import Album, AlbumPhoto
from app.models.photo import Photo
from app.models.user import User
from app.services.storage import generate_presigned_url

router = APIRouter(prefix="/albums", tags=["albums"])


class CreateAlbumPayload(BaseModel):
    name: str


class UpdateAlbumPayload(BaseModel):
    name: str | None = None
    cover_photo_id: str | None = None


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


@router.post("")
async def create_album(
    payload: CreateAlbumPayload,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Album name is required")
    if len(name) > 100:
        raise HTTPException(status_code=400, detail="Album name must be 100 characters or fewer")

    album = Album(user_id=current_user.id, name=name)
    db.add(album)
    await db.commit()
    await db.refresh(album)

    return {
        "id": str(album.id),
        "name": album.name,
        "cover_photo_id": None,
        "photo_count": 0,
        "cover_thumbnail_url": None,
    }


@router.get("/{album_id}")
async def get_album(
    album_id: str = Path(...),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        album_uuid = UUID(album_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid album id") from exc

    album_result = await db.execute(
        select(Album).where(Album.id == album_uuid, Album.user_id == current_user.id)
    )
    album = album_result.scalar_one_or_none()
    if album is None:
        raise HTTPException(status_code=404, detail="Album not found")

    count_result = await db.execute(
        select(func.count())
        .select_from(AlbumPhoto)
        .where(AlbumPhoto.album_id == album.id)
    )
    photo_count = int(count_result.scalar_one() or 0)

    photos_result = await db.execute(
        select(
            Photo.id,
            Photo.thumbnail_key,
            Photo.taken_at,
            AlbumPhoto.position,
        )
        .join(AlbumPhoto, AlbumPhoto.photo_id == Photo.id)
        .where(AlbumPhoto.album_id == album.id)
        .order_by(AlbumPhoto.position.asc())
        .limit(limit)
        .offset(offset)
    )
    photo_rows = photos_result.mappings().all()

    photos = []
    for row in photo_rows:
        photos.append(
            {
                "id": str(row["id"]),
                "position": int(row["position"]),
                "taken_at": row["taken_at"].isoformat() if row["taken_at"] else None,
                "thumbnail_url": (
                    generate_presigned_url(row["thumbnail_key"])
                    if row["thumbnail_key"]
                    else None
                ),
            }
        )

    return {
        "id": str(album.id),
        "name": album.name,
        "cover_photo_id": str(album.cover_photo_id) if album.cover_photo_id else None,
        "photo_count": photo_count,
        "photos": photos,
    }


@router.patch("/{album_id}")
async def update_album(
    payload: UpdateAlbumPayload,
    album_id: str = Path(...),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        album_uuid = UUID(album_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid album id") from exc

    album_result = await db.execute(
        select(Album).where(Album.id == album_uuid, Album.user_id == current_user.id)
    )
    album = album_result.scalar_one_or_none()
    if album is None:
        raise HTTPException(status_code=404, detail="Album not found")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Album name is required")
        if len(name) > 100:
            raise HTTPException(status_code=400, detail="Album name must be 100 characters or fewer")
        album.name = name

    if payload.cover_photo_id is not None:
        try:
            cover_photo_uuid = UUID(payload.cover_photo_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid cover_photo_id") from exc

        photo_result = await db.execute(
            select(Photo).where(Photo.id == cover_photo_uuid, Photo.user_id == current_user.id)
        )
        photo = photo_result.scalar_one_or_none()
        if photo is None:
            raise HTTPException(status_code=400, detail="Cover photo must belong to current user")

        in_album_result = await db.execute(
            select(AlbumPhoto).where(
                AlbumPhoto.album_id == album.id,
                AlbumPhoto.photo_id == cover_photo_uuid,
            )
        )
        in_album = in_album_result.scalar_one_or_none()
        if in_album is None:
            raise HTTPException(status_code=400, detail="Cover photo must be part of the album")

        album.cover_photo_id = cover_photo_uuid

    await db.commit()
    await db.refresh(album)

    cover_thumbnail_url = None
    if album.cover_photo_id:
        cover_result = await db.execute(select(Photo.thumbnail_key).where(Photo.id == album.cover_photo_id))
        cover_key = cover_result.scalar_one_or_none()
        if cover_key:
            cover_thumbnail_url = generate_presigned_url(cover_key)

    return {
        "id": str(album.id),
        "name": album.name,
        "cover_photo_id": str(album.cover_photo_id) if album.cover_photo_id else None,
        "cover_thumbnail_url": cover_thumbnail_url,
    }
