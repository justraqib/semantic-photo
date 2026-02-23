from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_current_user
from app.core.database import get_db
from app.models.photo import Photo
from app.models.user import User
from app.services.dedup import compute_phash, is_duplicate
from app.services.exif import extract_exif
from app.services.storage import upload_file
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

        upload_file(file_bytes, storage_key, file.content_type)
        upload_file(thumbnail_bytes, thumbnail_key, "image/webp")

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
        uploaded_count += 1

    await db.commit()
    return {"uploaded": uploaded_count, "skipped": skipped_count}
