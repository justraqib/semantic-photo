from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_current_user
from app.core.database import get_db
from app.jobs.queue import push_embedding_job
from app.models.photo import Photo
from app.models.user import User
from app.services.dedup import compute_phash, is_duplicate
from app.services.exif import extract_exif
from app.services.storage import generate_presigned_url, upload_file
from app.services.thumbnail import generate_thumbnail

router = APIRouter(prefix="/photos", tags=["photos"])

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
JPEG_MAGIC = b"\xFF\xD8\xFF"
PNG_MAGIC = b"\x89PNG"


def _parse_taken_at(exif_taken_at: str | None) -> datetime | None:
    if not exif_taken_at:
        return None
    try:
        return datetime.strptime(exif_taken_at, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


@router.post("/upload")
async def upload_photos(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    uploaded_count = 0
    skipped_count = 0
    user_id = str(current_user.id)
    queued_photo_ids: list[str] = []

    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid MIME type for {file.filename}. Only image/* is allowed.",
            )

        file_bytes = await file.read()

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"{file.filename} exceeds 50MB limit.",
            )

        if file.content_type in {"image/jpeg", "image/jpg"} and not file_bytes.startswith(JPEG_MAGIC):
            raise HTTPException(
                status_code=422,
                detail=f"Magic bytes do not match claimed type for {file.filename} (expected JPEG).",
            )

        if file.content_type == "image/png" and not file_bytes.startswith(PNG_MAGIC):
            raise HTTPException(
                status_code=422,
                detail=f"Magic bytes do not match claimed type for {file.filename} (expected PNG).",
            )

        phash_str = compute_phash(file_bytes)
        if await is_duplicate(phash_str, user_id, db):
            skipped_count += 1
            continue

        thumbnail_bytes = generate_thumbnail(file_bytes)
        exif = extract_exif(file_bytes)

        storage_key = f"users/{user_id}/photos/{uuid4()}.jpg"
        thumbnail_key = f"users/{user_id}/thumbnails/{uuid4()}.webp"

        try:
            upload_file(file_bytes, storage_key, file.content_type)
            upload_file(thumbnail_bytes, thumbnail_key, "image/webp")
        except ValueError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Upload storage is not configured: {exc}",
            ) from exc
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "UnknownError")
            if error_code == "AccessDenied":
                raise HTTPException(
                    status_code=503,
                    detail="Upload storage access denied. Check Cloudflare R2 token permissions and bucket name.",
                ) from exc
            raise HTTPException(
                status_code=503,
                detail=f"Upload to storage failed: {error_code}",
            ) from exc
        except BotoCoreError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Upload to storage failed: {exc.__class__.__name__}",
            ) from exc

        photo = Photo(
            user_id=current_user.id,
            storage_key=storage_key,
            thumbnail_key=thumbnail_key,
            original_filename=file.filename,
            file_size_bytes=len(file_bytes),
            mime_type=file.content_type,
            width=exif.get("width"),
            height=exif.get("height"),
            taken_at=_parse_taken_at(exif.get("taken_at")),
            source="manual_upload",
            source_id=None,
            phash=phash_str,
            embedding=None,
            caption=None,
            gps_lat=exif.get("gps_lat"),
            gps_lng=exif.get("gps_lng"),
            camera_make=exif.get("camera_make"),
            is_deleted=False,
        )
        db.add(photo)
        queued_photo_ids.append(str(photo.id))
        uploaded_count += 1

    await db.commit()

    for photo_id in queued_photo_ids:
        push_embedding_job(photo_id)

    return {"uploaded": uploaded_count, "skipped": skipped_count}


@router.get("")
async def list_photos(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Photo)
        .where(Photo.user_id == current_user.id, Photo.is_deleted.is_(False))
        .order_by(Photo.taken_at.desc().nullslast(), desc(Photo.uploaded_at))
    )

    parsed_cursor: datetime | None = None
    if cursor:
        try:
            parsed_cursor = datetime.fromisoformat(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid cursor format. Use ISO datetime.") from exc
        query = query.where(Photo.uploaded_at < parsed_cursor)

    result = await db.execute(query.limit(limit))
    photos = result.scalars().all()

    items = []
    for photo in photos:
        thumbnail_url = generate_presigned_url(photo.thumbnail_key) if photo.thumbnail_key else None
        items.append(
            {
                "id": str(photo.id),
                "thumbnail_key": photo.thumbnail_key,
                "thumbnail_url": thumbnail_url,
                "taken_at": photo.taken_at.isoformat() if photo.taken_at else None,
                "uploaded_at": photo.uploaded_at.isoformat() if photo.uploaded_at else None,
            }
        )

    next_cursor = None
    if photos and len(photos) == limit and photos[-1].uploaded_at:
        next_cursor = photos[-1].uploaded_at.isoformat()

    return {"items": items, "next_cursor": next_cursor}


@router.get("/map")
async def list_map_photos(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Photo.id, Photo.gps_lat, Photo.gps_lng, Photo.thumbnail_key)
        .where(
            Photo.user_id == current_user.id,
            Photo.is_deleted.is_(False),
            Photo.gps_lat.is_not(None),
            Photo.gps_lng.is_not(None),
        )
    )
    rows = result.all()
    return [
        {
            "id": str(photo_id),
            "gps_lat": gps_lat,
            "gps_lng": gps_lng,
            "thumbnail_key": thumbnail_key,
            "thumbnail_url": generate_presigned_url(thumbnail_key) if thumbnail_key else None,
        }
        for photo_id, gps_lat, gps_lng, thumbnail_key in rows
    ]


@router.get("/{photo_id}")
async def get_photo(
    photo_id: str = Path(...),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        photo_uuid = UUID(photo_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid photo id") from exc

    result = await db.execute(
        select(Photo).where(
            Photo.id == photo_uuid,
            Photo.user_id == current_user.id,
            Photo.is_deleted.is_(False),
        )
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    full_url = generate_presigned_url(photo.storage_key)

    return {
        "id": str(photo.id),
        "storage_key": photo.storage_key,
        "url": full_url,
        "mime_type": photo.mime_type,
        "taken_at": photo.taken_at.isoformat() if photo.taken_at else None,
        "uploaded_at": photo.uploaded_at.isoformat() if photo.uploaded_at else None,
    }


@router.delete("/{photo_id}")
async def delete_photo(
    photo_id: str = Path(...),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        photo_uuid = UUID(photo_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid photo id") from exc

    result = await db.execute(select(Photo).where(Photo.id == photo_uuid))
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    if photo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    photo.is_deleted = True
    await db.commit()

    return {"message": "Photo soft-deleted"}
