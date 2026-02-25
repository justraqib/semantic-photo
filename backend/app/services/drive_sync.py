from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.jobs.queue import push_embedding_job
from app.models.drive import DriveSyncState
from app.models.photo import Photo
from app.models.user import OAuthAccount
from app.services.dedup import compute_phash, is_duplicate
from app.services.exif import extract_exif
from app.services.storage import upload_file
from app.services.thumbnail import generate_thumbnail
from app.services.zip_utils import extract_image_files_from_zip, is_zip_upload

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
GOOGLE_DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"


def _parse_taken_at(exif_taken_at: str | None) -> datetime | None:
    if not exif_taken_at:
        return None
    try:
        return datetime.strptime(exif_taken_at, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _looks_like_image(filename: str, mime_type: str) -> bool:
    if mime_type.startswith("image/"):
        return True
    lower = filename.lower()
    return lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp", ".tiff"))


def _looks_like_supported_drive_file(filename: str, mime_type: str) -> bool:
    if _looks_like_image(filename, mime_type):
        return True
    return is_zip_upload(filename, mime_type)


async def refresh_access_token(refresh_token: str) -> str:
    payload = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data=payload)
    response.raise_for_status()
    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError("Google OAuth response did not include access_token")
    return access_token


async def _list_drive_children(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    folder_id: str,
) -> list[dict]:
    files: list[dict] = []
    page_token: str | None = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed=false",
            "fields": "nextPageToken,files(id,name,mimeType,trashed)",
            "pageSize": "1000",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token

        response = await client.get(
            f"{GOOGLE_DRIVE_API_BASE}/files",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        payload = response.json()
        files.extend(payload.get("files", []))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return files


async def _collect_drive_images(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    root_folder_id: str,
) -> list[dict]:
    queue = [root_folder_id]
    images: list[dict] = []

    while queue:
        current_folder = queue.pop(0)
        children = await _list_drive_children(client, headers, current_folder)
        for item in children:
            mime_type = item.get("mimeType", "")
            if mime_type == GOOGLE_DRIVE_FOLDER_MIME:
                queue.append(item["id"])
                continue
            if _looks_like_supported_drive_file(item.get("name", ""), mime_type):
                images.append(item)

    return images


async def sync_user(user_id, db: AsyncSession) -> dict[str, int]:
    oauth_result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user_id,
            OAuthAccount.provider == "google",
        )
    )
    oauth_account = oauth_result.scalar_one_or_none()
    if oauth_account is None or not oauth_account.refresh_token:
        raise RuntimeError("Google refresh token not found for user")

    state_result = await db.execute(select(DriveSyncState).where(DriveSyncState.user_id == user_id))
    state = state_result.scalar_one_or_none()
    if state is None:
        state = DriveSyncState(user_id=user_id, sync_enabled=True)
        db.add(state)
        await db.flush()

    if not state.folder_id:
        raise RuntimeError("Drive folder is not selected.")

    try:
        access_token = await refresh_access_token(oauth_account.refresh_token)
    except Exception:
        state.sync_enabled = False
        state.last_error = "Google account disconnected. Please reconnect."
        await db.commit()
        return {"total": 0, "uploaded": 0, "skipped": 0, "failed": 0}

    headers = {"Authorization": f"Bearer {access_token}"}
    uploaded = 0
    skipped = 0
    failed = 0
    total = 0
    max_upload_bytes = 50 * 1024 * 1024

    async with httpx.AsyncClient(timeout=60.0) as client:
        image_files = await _collect_drive_images(client, headers, state.folder_id)

        for file_data in image_files:
            source_id = file_data.get("id")
            mime_type = file_data.get("mimeType") or "image/jpeg"
            file_name = file_data.get("name") or f"{source_id}.jpg"
            if not source_id:
                failed += 1
                continue

            if _looks_like_image(file_name, mime_type):
                total += 1
                existing_photo_result = await db.execute(
                    select(Photo.id).where(
                        Photo.user_id == user_id,
                        Photo.source == "google_drive",
                        Photo.source_id == source_id,
                    )
                )
                if existing_photo_result.scalar_one_or_none():
                    skipped += 1
                    continue

                try:
                    file_response = await client.get(
                        f"{GOOGLE_DRIVE_API_BASE}/files/{source_id}",
                        headers=headers,
                        params={"alt": "media"},
                    )
                    file_response.raise_for_status()
                    file_bytes = file_response.content

                    if len(file_bytes) > max_upload_bytes:
                        skipped += 1
                        continue

                    phash_str = compute_phash(file_bytes)
                    if await is_duplicate(phash_str, str(user_id), db):
                        skipped += 1
                        continue

                    thumbnail_bytes = generate_thumbnail(file_bytes)
                    exif = extract_exif(file_bytes)

                    storage_key = f"users/{user_id}/photos/{uuid4()}.jpg"
                    thumbnail_key = f"users/{user_id}/thumbnails/{uuid4()}.webp"
                    upload_file(file_bytes, storage_key, mime_type)
                    upload_file(thumbnail_bytes, thumbnail_key, "image/webp")

                    photo = Photo(
                        user_id=user_id,
                        storage_key=storage_key,
                        thumbnail_key=thumbnail_key,
                        original_filename=file_name,
                        file_size_bytes=len(file_bytes),
                        mime_type=mime_type,
                        width=exif.get("width"),
                        height=exif.get("height"),
                        taken_at=_parse_taken_at(exif.get("taken_at")),
                        source="google_drive",
                        source_id=source_id,
                        phash=phash_str,
                        embedding=None,
                        caption=None,
                        gps_lat=exif.get("gps_lat"),
                        gps_lng=exif.get("gps_lng"),
                        camera_make=exif.get("camera_make"),
                        is_deleted=False,
                    )
                    db.add(photo)
                    await db.flush()
                    push_embedding_job(str(photo.id))
                    uploaded += 1
                except Exception as exc:
                    failed += 1
                    print(f"Drive sync for user {user_id}: failed processing file {source_id}: {exc}")
                    continue
                continue

            if is_zip_upload(file_name, mime_type):
                try:
                    file_response = await client.get(
                        f"{GOOGLE_DRIVE_API_BASE}/files/{source_id}",
                        headers=headers,
                        params={"alt": "media"},
                    )
                    file_response.raise_for_status()
                    zip_bytes = file_response.content
                    entries = extract_image_files_from_zip(zip_bytes, max_upload_bytes)
                except Exception as exc:
                    failed += 1
                    print(f"Drive sync for user {user_id}: failed reading zip {source_id}: {exc}")
                    continue

                for entry_name, entry_bytes, entry_content_type in entries:
                    total += 1
                    source_entry_id = f"{source_id}:{entry_name}"
                    existing_photo_result = await db.execute(
                        select(Photo.id).where(
                            Photo.user_id == user_id,
                            Photo.source == "google_drive",
                            Photo.source_id == source_entry_id,
                        )
                    )
                    if existing_photo_result.scalar_one_or_none():
                        skipped += 1
                        continue

                    try:
                        phash_str = compute_phash(entry_bytes)
                        if await is_duplicate(phash_str, str(user_id), db):
                            skipped += 1
                            continue

                        thumbnail_bytes = generate_thumbnail(entry_bytes)
                        exif = extract_exif(entry_bytes)
                        storage_key = f"users/{user_id}/photos/{uuid4()}.jpg"
                        thumbnail_key = f"users/{user_id}/thumbnails/{uuid4()}.webp"
                        upload_file(entry_bytes, storage_key, entry_content_type)
                        upload_file(thumbnail_bytes, thumbnail_key, "image/webp")

                        photo = Photo(
                            user_id=user_id,
                            storage_key=storage_key,
                            thumbnail_key=thumbnail_key,
                            original_filename=entry_name,
                            file_size_bytes=len(entry_bytes),
                            mime_type=entry_content_type,
                            width=exif.get("width"),
                            height=exif.get("height"),
                            taken_at=_parse_taken_at(exif.get("taken_at")),
                            source="google_drive",
                            source_id=source_entry_id,
                            phash=phash_str,
                            embedding=None,
                            caption=None,
                            gps_lat=exif.get("gps_lat"),
                            gps_lng=exif.get("gps_lng"),
                            camera_make=exif.get("camera_make"),
                            is_deleted=False,
                        )
                        db.add(photo)
                        await db.flush()
                        push_embedding_job(str(photo.id))
                        uploaded += 1
                    except Exception as exc:
                        failed += 1
                        print(f"Drive sync for user {user_id}: failed zip entry {source_entry_id}: {exc}")
                        continue

    state.last_sync_at = datetime.now(timezone.utc)
    state.last_error = None
    state.next_page_token = None
    await db.commit()
    return {"total": total, "uploaded": uploaded, "skipped": skipped, "failed": failed}


async def sync_all_users() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DriveSyncState.user_id).where(DriveSyncState.sync_enabled.is_(True))
        )
        user_ids = [row[0] for row in result.all()]

    for user_id in user_ids:
        async with AsyncSessionLocal() as db:
            try:
                await sync_user(user_id, db)
            except Exception as exc:
                print(f"Drive sync for user {user_id} failed: {exc}")
