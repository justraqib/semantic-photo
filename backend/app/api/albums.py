import secrets
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


class AddAlbumPhotosPayload(BaseModel):
    photo_ids: list[str]


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
            Album.is_public,
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
                "is_public": bool(row["is_public"]),
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
        "is_public": bool(album.is_public),
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
        "is_public": bool(album.is_public),
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
        "is_public": bool(album.is_public),
    }


@router.delete("/{album_id}")
async def delete_album(
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

    await db.delete(album)
    await db.commit()
    return {"ok": True}


@router.post("/{album_id}/share")
async def enable_album_share(
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

    if not album.public_token:
        album.public_token = secrets.token_urlsafe(24)
    album.is_public = True
    await db.commit()
    await db.refresh(album)

    return {
        "is_public": True,
        "public_token": album.public_token,
        "public_url": f"/albums/public/{album.public_token}",
    }


@router.delete("/{album_id}/share")
async def disable_album_share(
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

    album.is_public = False
    album.public_token = None
    await db.commit()
    return {"is_public": False}


@router.get("/public/{token}")
async def get_public_album(
    token: str = Path(..., min_length=8),
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Album).where(Album.public_token == token, Album.is_public.is_(True))
    )
    album = result.scalar_one_or_none()
    if album is None:
        raise HTTPException(status_code=404, detail="Public album not found")

    photos_result = await db.execute(
        select(Photo.id, Photo.thumbnail_key, Photo.storage_key, Photo.taken_at, AlbumPhoto.position)
        .join(AlbumPhoto, AlbumPhoto.photo_id == Photo.id)
        .where(AlbumPhoto.album_id == album.id, Photo.is_deleted.is_(False))
        .order_by(AlbumPhoto.position.asc())
        .limit(limit)
        .offset(offset)
    )
    rows = photos_result.mappings().all()

    photos = []
    for row in rows:
        photos.append(
            {
                "id": str(row["id"]),
                "taken_at": row["taken_at"].isoformat() if row["taken_at"] else None,
                "thumbnail_url": generate_presigned_url(row["thumbnail_key"]) if row["thumbnail_key"] else None,
                "url": generate_presigned_url(row["storage_key"]) if row["storage_key"] else None,
            }
        )

    return {
        "name": album.name,
        "photos": photos,
    }


@router.post("/{album_id}/photos")
async def add_photos_to_album(
    payload: AddAlbumPhotosPayload,
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

    max_position_result = await db.execute(
        select(func.max(AlbumPhoto.position)).where(AlbumPhoto.album_id == album.id)
    )
    next_position = (max_position_result.scalar_one() or 0) + 1

    inserted_count = 0
    for photo_id_str in payload.photo_ids:
        try:
            photo_uuid = UUID(photo_id_str)
        except ValueError:
            continue

        photo_result = await db.execute(
            select(Photo.id).where(Photo.id == photo_uuid, Photo.user_id == current_user.id)
        )
        if photo_result.scalar_one_or_none() is None:
            continue

        existing_result = await db.execute(
            select(AlbumPhoto).where(
                AlbumPhoto.album_id == album.id,
                AlbumPhoto.photo_id == photo_uuid,
            )
        )
        if existing_result.scalar_one_or_none():
            continue

        db.add(
            AlbumPhoto(
                album_id=album.id,
                photo_id=photo_uuid,
                position=next_position,
            )
        )
        next_position += 1
        inserted_count += 1

    await db.commit()
    return {"ok": True, "inserted": inserted_count}


@router.delete("/{album_id}/photos/{photo_id}")
async def remove_photo_from_album(
    album_id: str = Path(...),
    photo_id: str = Path(...),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        album_uuid = UUID(album_id)
        photo_uuid = UUID(photo_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid album or photo id") from exc

    album_result = await db.execute(
        select(Album).where(Album.id == album_uuid, Album.user_id == current_user.id)
    )
    album = album_result.scalar_one_or_none()
    if album is None:
        raise HTTPException(status_code=404, detail="Album not found")

    link_result = await db.execute(
        select(AlbumPhoto).where(
            AlbumPhoto.album_id == album.id,
            AlbumPhoto.photo_id == photo_uuid,
        )
    )
    link = link_result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Photo not found in album")

    await db.delete(link)
    await db.commit()
    return {"ok": True}
