from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path as FilePath
from uuid import UUID, uuid4

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel
from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_current_user
from app.core.database import get_db
from app.jobs.queue import get_embedding_queue_length, push_embedding_job
from app.models.photo import Photo
from app.models.tag import PhotoTag, Tag
from app.models.user import User
from app.services.dedup import compute_phash
from app.services.exif import extract_exif
from app.services.people import PERSON_CLUSTER_PREFIX, PERSON_NAME_PREFIX, auto_assign_person_cluster
from app.services.storage import delete_file, generate_presigned_url, get_file, upload_file
from app.services.thumbnail import generate_thumbnail
from app.services.zip_utils import detect_image_content_type, extract_image_files_from_zip, is_zip_upload

router = APIRouter(prefix="/photos", tags=["photos"])

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
JPEG_MAGIC = b"\xFF\xD8\xFF"
PNG_MAGIC = b"\x89PNG"


class DuplicateDeletePayload(BaseModel):
    photo_ids: list[str]


def _person_tag_filter():
    return or_(
        Tag.name.like(f"{PERSON_NAME_PREFIX}%"),
        Tag.name.like(f"{PERSON_CLUSTER_PREFIX}%"),
    )


def _parse_taken_at(exif_taken_at: str | None) -> datetime | None:
    if not exif_taken_at:
        return None
    try:
        return datetime.strptime(exif_taken_at, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _assert_magic_bytes(content_type: str, file_bytes: bytes, filename: str) -> None:
    if content_type in {"image/jpeg", "image/jpg"} and not file_bytes.startswith(JPEG_MAGIC):
        raise HTTPException(
            status_code=422,
            detail=f"Magic bytes do not match claimed type for {filename} (expected JPEG).",
        )
    if content_type == "image/png" and not file_bytes.startswith(PNG_MAGIC):
        raise HTTPException(
            status_code=422,
            detail=f"Magic bytes do not match claimed type for {filename} (expected PNG).",
        )


def _normalize_image_content_type(filename: str, content_type: str | None, file_bytes: bytes) -> str:
    if content_type and content_type.startswith("image/"):
        return content_type
    detected = detect_image_content_type(filename, file_bytes)
    if detected:
        return detected
    return "application/octet-stream"


async def _expand_upload_files(files: list[UploadFile]) -> tuple[list[tuple[str, bytes, str]], int]:
    expanded_images: list[tuple[str, bytes, str]] = []
    failed_files = 0
    for file in files:
        filename = file.filename or "upload"
        file_bytes = await file.read()

        if is_zip_upload(filename, file.content_type):
            try:
                images = extract_image_files_from_zip(file_bytes, MAX_FILE_SIZE_BYTES)
            except ValueError:
                failed_files += 1
                continue
            for image_name, image_bytes, image_type in images:
                expanded_images.append((image_name, image_bytes, image_type))
            continue

        content_type = _normalize_image_content_type(filename, file.content_type, file_bytes)
        if not content_type.startswith("image/"):
            failed_files += 1
            continue
        expanded_images.append((filename, file_bytes, content_type))

    return expanded_images, failed_files


@router.post("/upload/preview")
async def preview_upload_photos(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    expanded_images, failed_files = await _expand_upload_files(files)

    already_uploaded = 0
    duplicates_in_selection = 0
    new_photos = 0

    for image_name, image_bytes, image_content_type in expanded_images:
        if len(image_bytes) > MAX_FILE_SIZE_BYTES:
            failed_files += 1
            continue

        try:
            _assert_magic_bytes(image_content_type, image_bytes, image_name)
        except HTTPException:
            failed_files += 1
            continue

        try:
            phash_str = compute_phash(image_bytes)
        except Exception:
            failed_files += 1
            continue

        _ = phash_str
        new_photos += 1

    total_selected = len(expanded_images)

    return {
        "total_selected": total_selected,
        "already_uploaded": already_uploaded,
        "duplicates_in_selection": duplicates_in_selection,
        "new_photos": new_photos,
        "failed": failed_files,
    }


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
    failed_count = 0
    queued_photo_ids: list[str] = []

    expanded_images, failed_files = await _expand_upload_files(files)
    failed_count += failed_files

    for image_name, image_bytes, image_content_type in expanded_images:
        if len(image_bytes) > MAX_FILE_SIZE_BYTES:
            failed_count += 1
            continue

        try:
            _assert_magic_bytes(image_content_type, image_bytes, image_name)
        except HTTPException:
            failed_count += 1
            continue

        try:
            phash_str = compute_phash(image_bytes)
        except Exception:
            failed_count += 1
            continue

        thumbnail_bytes = generate_thumbnail(image_bytes)
        exif = extract_exif(image_bytes)

        storage_key = f"users/{user_id}/photos/{uuid4()}.jpg"
        thumbnail_key = f"users/{user_id}/thumbnails/{uuid4()}.webp"

        try:
            upload_file(image_bytes, storage_key, image_content_type)
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
            original_filename=image_name,
            file_size_bytes=len(image_bytes),
            mime_type=image_content_type,
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

    return {"uploaded": uploaded_count, "skipped": skipped_count, "failed": failed_count}


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
        .order_by(desc(Photo.uploaded_at), desc(Photo.id))
    )

    if cursor:
        cursor_parts = cursor.split("|", 1)
        if len(cursor_parts) == 2:
            cursor_dt_raw, cursor_id_raw = cursor_parts
            try:
                parsed_cursor = datetime.fromisoformat(cursor_dt_raw)
                parsed_cursor_id = UUID(cursor_id_raw)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid cursor format.") from exc
            query = query.where(
                or_(
                    Photo.uploaded_at < parsed_cursor,
                    and_(Photo.uploaded_at == parsed_cursor, Photo.id < parsed_cursor_id),
                )
            )
        else:
            # Backward compatibility for old cursor format.
            try:
                parsed_cursor = datetime.fromisoformat(cursor)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid cursor format.") from exc
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
        next_cursor = f"{photos[-1].uploaded_at.isoformat()}|{photos[-1].id}"

    return {"items": items, "next_cursor": next_cursor}


@router.get("/embedding-status")
async def embedding_status(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    pending_for_user = (
        await db.execute(
            select(func.count())
            .select_from(Photo)
            .where(
                Photo.user_id == current_user.id,
                Photo.is_deleted.is_(False),
                Photo.embedding.is_(None),
            )
        )
    ).scalar_one()
    ready_for_user = (
        await db.execute(
            select(func.count())
            .select_from(Photo)
            .where(
                Photo.user_id == current_user.id,
                Photo.is_deleted.is_(False),
                Photo.embedding.is_not(None),
            )
        )
    ).scalar_one()

    # CPU CLIP inference is usually around a couple of seconds per image.
    avg_seconds_per_image = 2
    pending = int(pending_for_user)
    ready = int(ready_for_user)
    total = pending + ready
    eta_seconds = pending * avg_seconds_per_image
    progress_percent = int((ready / total) * 100) if total else 100

    return {
        "pending_for_user": pending,
        "ready_for_user": ready,
        "total_for_user": total,
        "progress_percent": progress_percent,
        "queue_length": get_embedding_queue_length(),
        "avg_seconds_per_image": avg_seconds_per_image,
        "eta_seconds": eta_seconds,
    }


@router.post("/embedding/start")
async def start_embedding_for_pending(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Photo.id).where(
            Photo.user_id == current_user.id,
            Photo.is_deleted.is_(False),
            Photo.embedding.is_(None),
        )
    )
    photo_ids = [str(photo_id) for (photo_id,) in result.all()]
    for photo_id in photo_ids:
        push_embedding_job(photo_id, prioritize=True)

    return {
        "queued": len(photo_ids),
        "queue_length": get_embedding_queue_length(),
    }


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


@router.get("/trash")
async def list_trashed_photos(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Photo)
        .where(Photo.user_id == current_user.id, Photo.is_deleted.is_(True))
        .order_by(desc(Photo.uploaded_at), desc(Photo.id))
    )

    if cursor:
        cursor_parts = cursor.split("|", 1)
        if len(cursor_parts) == 2:
            cursor_dt_raw, cursor_id_raw = cursor_parts
            try:
                parsed_cursor = datetime.fromisoformat(cursor_dt_raw)
                parsed_cursor_id = UUID(cursor_id_raw)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid cursor format.") from exc
            query = query.where(
                or_(
                    Photo.uploaded_at < parsed_cursor,
                    and_(Photo.uploaded_at == parsed_cursor, Photo.id < parsed_cursor_id),
                )
            )
        else:
            try:
                parsed_cursor = datetime.fromisoformat(cursor)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid cursor format.") from exc
            query = query.where(Photo.uploaded_at < parsed_cursor)

    result = await db.execute(query.limit(limit))
    photos = result.scalars().all()

    items = []
    for photo in photos:
        items.append(
            {
                "id": str(photo.id),
                "thumbnail_url": generate_presigned_url(photo.thumbnail_key) if photo.thumbnail_key else None,
                "taken_at": photo.taken_at.isoformat() if photo.taken_at else None,
                "uploaded_at": photo.uploaded_at.isoformat() if photo.uploaded_at else None,
            }
        )

    next_cursor = None
    if photos and len(photos) == limit and photos[-1].uploaded_at:
        next_cursor = f"{photos[-1].uploaded_at.isoformat()}|{photos[-1].id}"

    return {"items": items, "next_cursor": next_cursor}


@router.get("/export")
async def export_photos_archive(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Photo).where(Photo.user_id == current_user.id, Photo.is_deleted.is_(False)).order_by(Photo.uploaded_at.asc())
    )
    photos = result.scalars().all()

    zip_buffer = io.BytesIO()
    metadata = []

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for photo in photos:
            if not photo.storage_key:
                continue

            try:
                file_bytes = get_file(photo.storage_key)
            except Exception:
                continue

            file_ext = FilePath(photo.original_filename or "").suffix or ".jpg"
            archive_name = f"photos/{photo.id}{file_ext}"
            zip_file.writestr(archive_name, file_bytes)

            metadata.append(
                {
                    "id": str(photo.id),
                    "original_filename": photo.original_filename,
                    "storage_key": photo.storage_key,
                    "thumbnail_key": photo.thumbnail_key,
                    "taken_at": photo.taken_at.isoformat() if photo.taken_at else None,
                    "uploaded_at": photo.uploaded_at.isoformat() if photo.uploaded_at else None,
                    "gps_lat": photo.gps_lat,
                    "gps_lng": photo.gps_lng,
                    "camera_make": photo.camera_make,
                    "source": photo.source,
                    "source_id": photo.source_id,
                }
            )

        zip_file.writestr("metadata/photos.json", json.dumps(metadata, ensure_ascii=True, indent=2))

    zip_buffer.seek(0)
    filename = f"photo-export-{current_user.id}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{photo_id}/restore")
async def restore_photo(
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
            Photo.is_deleted.is_(True),
        )
    )
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found in trash")

    photo.is_deleted = False
    await db.commit()
    return {"message": "Photo restored"}


@router.delete("/{photo_id}/hard")
async def hard_delete_photo(
    photo_id: str = Path(...),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        photo_uuid = UUID(photo_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid photo id") from exc

    result = await db.execute(
        select(Photo).where(Photo.id == photo_uuid, Photo.user_id == current_user.id)
    )
    photo = result.scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    if photo.storage_key:
        try:
            delete_file(photo.storage_key)
        except Exception:
            pass

    if photo.thumbnail_key:
        try:
            delete_file(photo.thumbnail_key)
        except Exception:
            pass

    await db.delete(photo)
    await db.commit()
    return {"message": "Photo permanently deleted"}


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


@router.get("/tools/duplicates")
async def list_duplicates(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    groups_stmt = (
        select(Photo.phash, func.count(Photo.id).label("count"))
        .where(
            Photo.user_id == current_user.id,
            Photo.is_deleted.is_(False),
            Photo.phash.is_not(None),
        )
        .group_by(Photo.phash)
        .having(func.count(Photo.id) > 1)
        .order_by(func.count(Photo.id).desc())
    )
    groups = (await db.execute(groups_stmt)).all()

    items = []
    for phash, count in groups:
        photos_stmt = (
            select(Photo)
            .where(
                Photo.user_id == current_user.id,
                Photo.is_deleted.is_(False),
                Photo.phash == phash,
            )
            .order_by(desc(Photo.uploaded_at))
        )
        photos = (await db.execute(photos_stmt)).scalars().all()
        items.append(
            {
                "phash": phash,
                "count": int(count),
                "photos": [
                    {
                        "id": str(photo.id),
                        "thumbnail_url": generate_presigned_url(photo.thumbnail_key) if photo.thumbnail_key else None,
                        "uploaded_at": photo.uploaded_at.isoformat() if photo.uploaded_at else None,
                        "taken_at": photo.taken_at.isoformat() if photo.taken_at else None,
                    }
                    for photo in photos
                ],
            }
        )

    return {"groups": items, "total_duplicates": sum(int(count) - 1 for _, count in groups)}


@router.post("/tools/duplicates/delete")
async def delete_duplicates(
    payload: DuplicateDeletePayload,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not payload.photo_ids:
        return {"deleted": 0}

    deleted = 0
    for raw_id in payload.photo_ids:
        try:
            photo_uuid = UUID(raw_id)
        except ValueError:
            continue

        result = await db.execute(
            select(Photo).where(
                Photo.id == photo_uuid,
                Photo.user_id == current_user.id,
                Photo.is_deleted.is_(False),
            )
        )
        photo = result.scalar_one_or_none()
        if not photo:
            continue

        if photo.storage_key:
            try:
                delete_file(photo.storage_key)
            except Exception:
                pass
        if photo.thumbnail_key:
            try:
                delete_file(photo.thumbnail_key)
            except Exception:
                pass

        await db.delete(photo)
        deleted += 1

    await db.commit()
    return {"deleted": deleted}


@router.post("/tools/duplicates/delete-all")
async def delete_all_duplicates(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    groups_stmt = (
        select(Photo.phash)
        .where(
            Photo.user_id == current_user.id,
            Photo.is_deleted.is_(False),
            Photo.phash.is_not(None),
        )
        .group_by(Photo.phash)
        .having(func.count(Photo.id) > 1)
    )
    duplicate_hashes = [row[0] for row in (await db.execute(groups_stmt)).all()]
    if not duplicate_hashes:
        return {"deleted": 0}

    deleted = 0
    for phash in duplicate_hashes:
        photos_stmt = (
            select(Photo)
            .where(
                Photo.user_id == current_user.id,
                Photo.is_deleted.is_(False),
                Photo.phash == phash,
            )
            .order_by(desc(Photo.uploaded_at), desc(Photo.id))
        )
        photos = (await db.execute(photos_stmt)).scalars().all()
        if len(photos) <= 1:
            continue

        # Keep newest photo, delete all others.
        for photo in photos[1:]:
            if photo.storage_key:
                try:
                    delete_file(photo.storage_key)
                except Exception:
                    pass
            if photo.thumbnail_key:
                try:
                    delete_file(photo.thumbnail_key)
                except Exception:
                    pass
            await db.delete(photo)
            deleted += 1

    await db.commit()
    return {"deleted": deleted}


@router.get("/meta/people")
async def list_people_groups(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    tag_stmt = (
        select(Tag.id, Tag.name, func.count(PhotoTag.photo_id).label("count"))
        .join(PhotoTag, PhotoTag.tag_id == Tag.id)
        .join(Photo, Photo.id == PhotoTag.photo_id)
        .where(
            Photo.user_id == current_user.id,
            Photo.is_deleted.is_(False),
            _person_tag_filter(),
        )
        .group_by(Tag.id, Tag.name)
        .order_by(func.count(PhotoTag.photo_id).desc())
    )
    groups = (await db.execute(tag_stmt)).all()

    people = []
    tagged_photo_ids: set[UUID] = set()
    for tag_id, tag_name, count in groups:
        photos_stmt = (
            select(Photo)
            .join(PhotoTag, PhotoTag.photo_id == Photo.id)
            .where(
                Photo.user_id == current_user.id,
                Photo.is_deleted.is_(False),
                PhotoTag.tag_id == tag_id,
            )
            .order_by(desc(Photo.uploaded_at))
            .limit(16)
        )
        photos = (await db.execute(photos_stmt)).scalars().all()
        tagged_photo_ids.update(photo.id for photo in photos)
        people.append(
            {
                "id": str(tag_id),
                "name": (
                    tag_name.replace(PERSON_NAME_PREFIX, "", 1).strip()
                    if tag_name.startswith(PERSON_NAME_PREFIX)
                    else "Unknown"
                ),
                "count": int(count),
                "group_type": "named" if tag_name.startswith(PERSON_NAME_PREFIX) else "cluster",
                "photos": [
                    {
                        "id": str(photo.id),
                        "thumbnail_url": generate_presigned_url(photo.thumbnail_key) if photo.thumbnail_key else None,
                    }
                    for photo in photos
                ],
            }
        )

    unknown_base_filter = (
        Photo.user_id == current_user.id,
        Photo.is_deleted.is_(False),
        ~Photo.id.in_(
            select(PhotoTag.photo_id)
            .join(Tag, Tag.id == PhotoTag.tag_id)
            .where(_person_tag_filter())
        ),
    )
    unknown_count_stmt = select(func.count(Photo.id)).where(*unknown_base_filter)
    unknown_count = int((await db.execute(unknown_count_stmt)).scalar() or 0)

    unknown_preview_stmt = (
        select(Photo)
        .where(*unknown_base_filter)
        .order_by(desc(Photo.uploaded_at))
        .limit(24)
    )
    unknown_photos = (await db.execute(unknown_preview_stmt)).scalars().all()
    if unknown_count > 0:
        people.append(
            {
                "id": "unknown",
                "name": "Unknown",
                "count": unknown_count,
                "group_type": "unassigned",
                "photos": [
                    {
                        "id": str(photo.id),
                        "thumbnail_url": generate_presigned_url(photo.thumbnail_key) if photo.thumbnail_key else None,
                    }
                    for photo in unknown_photos
                ],
            }
        )

    return {"people": people}


@router.get("/meta/people/{group_id}")
async def people_group_photos(
    group_id: str,
    limit: int = Query(default=60, ge=1, le=300),
    cursor: str | None = Query(default=None),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_filters = [
        Photo.user_id == current_user.id,
        Photo.is_deleted.is_(False),
    ]
    if group_id == "unknown":
        base_filters.append(
            ~Photo.id.in_(
                select(PhotoTag.photo_id)
                .join(Tag, Tag.id == PhotoTag.tag_id)
                .where(_person_tag_filter())
            )
        )
    else:
        try:
            group_uuid = UUID(group_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid people group id.") from exc

        group_exists = (
            await db.execute(
                select(func.count())
                .select_from(PhotoTag)
                .join(Photo, Photo.id == PhotoTag.photo_id)
                .where(
                    PhotoTag.tag_id == group_uuid,
                    Photo.user_id == current_user.id,
                    Photo.is_deleted.is_(False),
                )
            )
        ).scalar_one()
        if not group_exists:
            raise HTTPException(status_code=404, detail="People group not found.")

        base_filters.append(
            Photo.id.in_(
                select(PhotoTag.photo_id).where(PhotoTag.tag_id == group_uuid)
            )
        )

    stmt = select(Photo).where(*base_filters).order_by(desc(Photo.uploaded_at), desc(Photo.id))
    if cursor:
        cursor_parts = cursor.split("|", 1)
        if len(cursor_parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid cursor format.")
        cursor_dt_raw, cursor_id_raw = cursor_parts
        try:
            parsed_cursor = datetime.fromisoformat(cursor_dt_raw)
            parsed_cursor_id = UUID(cursor_id_raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid cursor format.") from exc
        stmt = stmt.where(
            or_(
                Photo.uploaded_at < parsed_cursor,
                and_(Photo.uploaded_at == parsed_cursor, Photo.id < parsed_cursor_id),
            )
        )

    photos = (await db.execute(stmt.limit(limit))).scalars().all()
    total_count = int(
        (
            await db.execute(
                select(func.count()).select_from(Photo).where(*base_filters)
            )
        ).scalar_one()
    )

    items = [
        {
            "id": str(photo.id),
            "thumbnail_url": generate_presigned_url(photo.thumbnail_key) if photo.thumbnail_key else None,
            "uploaded_at": photo.uploaded_at.isoformat() if photo.uploaded_at else None,
            "taken_at": photo.taken_at.isoformat() if photo.taken_at else None,
        }
        for photo in photos
    ]
    next_cursor = None
    if photos and len(photos) == limit and photos[-1].uploaded_at:
        next_cursor = f"{photos[-1].uploaded_at.isoformat()}|{photos[-1].id}"

    return {"items": items, "next_cursor": next_cursor, "total_count": total_count}


class PeopleAssignPayload(BaseModel):
    photo_ids: list[str]
    name: str


@router.post("/meta/people/assign")
async def assign_people_name(
    payload: PeopleAssignPayload,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    normalized = payload.name.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Name is required.")

    tag_name = f"{PERSON_NAME_PREFIX}{normalized.lower()}"
    tag = (
        await db.execute(select(Tag).where(Tag.name == tag_name))
    ).scalar_one_or_none()
    if tag is None:
        tag = Tag(name=tag_name)
        db.add(tag)
        await db.flush()

    valid_ids: list[UUID] = []
    for raw_id in payload.photo_ids:
        try:
            photo_uuid = UUID(raw_id)
        except ValueError:
            continue
        valid_ids.append(photo_uuid)

    if not valid_ids:
        return {"assigned": 0}

    photos = (
        await db.execute(
            select(Photo).where(
                Photo.id.in_(valid_ids),
                Photo.user_id == current_user.id,
                Photo.is_deleted.is_(False),
            )
        )
    ).scalars().all()

    assigned = 0
    for photo in photos:
        await db.execute(
            PhotoTag.__table__.delete().where(
                PhotoTag.photo_id == photo.id,
                PhotoTag.tag_id.in_(
                    select(Tag.id).where(_person_tag_filter())
                ),
            )
        )
        db.add(PhotoTag(photo_id=photo.id, tag_id=tag.id, confidence=1.0, source="manual_person"))
        assigned += 1

    await db.commit()
    return {"assigned": assigned, "name": normalized}


class PeopleRemovePayload(BaseModel):
    photo_ids: list[str]


@router.post("/meta/people/remove")
async def remove_from_people_group(
    payload: PeopleRemovePayload,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    valid_ids: list[UUID] = []
    for raw_id in payload.photo_ids:
        try:
            valid_ids.append(UUID(raw_id))
        except ValueError:
            continue
    if not valid_ids:
        return {"removed": 0}

    photos = (
        await db.execute(
            select(Photo.id).where(
                Photo.id.in_(valid_ids),
                Photo.user_id == current_user.id,
                Photo.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    if not photos:
        return {"removed": 0}

    await db.execute(
        PhotoTag.__table__.delete().where(
            PhotoTag.photo_id.in_(photos),
            PhotoTag.tag_id.in_(
                select(Tag.id).where(_person_tag_filter())
            ),
        )
    )
    await db.commit()
    return {"removed": len(photos)}


@router.post("/meta/people/reindex")
async def reindex_people_groups(
    full_reset: bool = Query(default=False),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    if full_reset:
        await db.execute(
            PhotoTag.__table__.delete().where(
                PhotoTag.photo_id.in_(
                    select(Photo.id).where(
                        Photo.user_id == current_user.id,
                        Photo.is_deleted.is_(False),
                    )
                ),
                PhotoTag.tag_id.in_(
                    select(Tag.id).where(_person_tag_filter())
                ),
            )
        )
        await db.commit()

    photos = (
        await db.execute(
            select(Photo)
            .where(
                Photo.user_id == current_user.id,
                Photo.is_deleted.is_(False),
                Photo.embedding.is_not(None),
            )
            .order_by(Photo.uploaded_at.asc())
        )
    ).scalars().all()

    processed = 0
    for index, photo in enumerate(photos, start=1):
        await auto_assign_person_cluster(db, photo)
        processed += 1
        if index % 100 == 0:
            await db.commit()

    await db.commit()
    return {"processed": processed}
