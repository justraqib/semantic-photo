from __future__ import annotations

import asyncio
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

_active_sync_tasks: dict[str, asyncio.Task[None]] = {}
_MAX_SYNC_IMAGE_BYTES = 50 * 1024 * 1024


def _parse_taken_at(exif_taken_at: str | None) -> datetime | None:
    if not exif_taken_at:
        return None
    try:
        return datetime.strptime(exif_taken_at, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


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


async def _ensure_state(user_id, db: AsyncSession) -> DriveSyncState:
    state_result = await db.execute(select(DriveSyncState).where(DriveSyncState.user_id == user_id))
    state = state_result.scalar_one_or_none()
    if state is None:
        state = DriveSyncState(user_id=user_id, sync_enabled=True)
        db.add(state)
        await db.flush()
    return state


async def _list_drive_folder_files(access_token: str, folder_id: str) -> list[dict]:
    files: list[dict] = []
    page_token: str | None = None
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=40.0) as client:
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


async def _download_drive_file(access_token: str, file_id: str) -> bytes:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            f"{GOOGLE_DRIVE_API_BASE}/files/{file_id}",
            headers=headers,
            params={"alt": "media"},
        )
        response.raise_for_status()
        return response.content


async def _source_exists(user_id, source_id: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(Photo.id).where(
            Photo.user_id == user_id,
            Photo.source == "google_drive",
            Photo.source_id == source_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def _ingest_drive_image(
    *,
    user_id,
    source_id: str,
    filename: str,
    mime_type: str,
    image_bytes: bytes,
    db: AsyncSession,
) -> str:
    phash_str = compute_phash(image_bytes)
    if await is_duplicate(phash_str, str(user_id), db):
        return "skipped"

    thumbnail_bytes = generate_thumbnail(image_bytes)
    exif = extract_exif(image_bytes)

    storage_key = f"users/{user_id}/photos/{uuid4()}.jpg"
    thumbnail_key = f"users/{user_id}/thumbnails/{uuid4()}.webp"
    upload_file(image_bytes, storage_key, mime_type)
    upload_file(thumbnail_bytes, thumbnail_key, "image/webp")

    photo = Photo(
        user_id=user_id,
        storage_key=storage_key,
        thumbnail_key=thumbnail_key,
        original_filename=filename,
        file_size_bytes=len(image_bytes),
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
    await db.commit()
    return "imported"


async def _update_state_counters(
    *,
    state: DriveSyncState,
    processed: int,
    imported: int,
    skipped: int,
    failed: int,
    pending: int,
    db: AsyncSession,
) -> None:
    state.processed_count = processed
    state.imported_count = imported
    state.skipped_count = skipped
    state.failed_count = failed
    state.pending_count = max(0, pending)
    await db.commit()


async def sync_user(user_id, db: AsyncSession) -> None:
    state = await _ensure_state(user_id, db)
    if state.status == "running":
        return

    state.status = "running"
    state.last_error = None
    state.pending_count = 0
    state.processed_count = 0
    state.imported_count = 0
    state.skipped_count = 0
    state.failed_count = 0
    await db.commit()

    oauth_result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user_id,
            OAuthAccount.provider == "google",
        )
    )
    oauth_account = oauth_result.scalar_one_or_none()
    if oauth_account is None or not oauth_account.refresh_token:
        state.status = "idle"
        state.last_error = "Google refresh token not found for user"
        await db.commit()
        return

    try:
        access_token = await refresh_access_token(oauth_account.refresh_token)
    except Exception:
        state.sync_enabled = False
        state.status = "idle"
        state.last_error = "Google account disconnected. Please reconnect."
        await db.commit()
        return

    if not state.folder_id:
        state.status = "idle"
        state.last_error = "Please choose a Google Drive folder first."
        await db.commit()
        return

    drive_files = await _list_drive_folder_files(access_token, state.folder_id)
    sync_candidates = [
        drive_file
        for drive_file in drive_files
        if (drive_file.get("mimeType") or "").startswith("image/")
        or is_zip_upload(drive_file.get("name"), drive_file.get("mimeType"))
    ]

    processed = 0
    imported = 0
    skipped = 0
    failed = 0
    pending = len(sync_candidates)
    await _update_state_counters(
        state=state,
        processed=processed,
        imported=imported,
        skipped=skipped,
        failed=failed,
        pending=pending,
        db=db,
    )

    for drive_file in sync_candidates:
        file_id = drive_file.get("id")
        file_name = drive_file.get("name") or "drive-image"
        mime_type = drive_file.get("mimeType") or "application/octet-stream"

        if not file_id:
            failed += 1
            processed += 1
            pending -= 1
            await _update_state_counters(
                state=state,
                processed=processed,
                imported=imported,
                skipped=skipped,
                failed=failed,
                pending=pending,
                db=db,
            )
            continue

        if mime_type.startswith("image/"):
            if await _source_exists(user_id, file_id, db):
                skipped += 1
            else:
                try:
                    image_bytes = await _download_drive_file(access_token, file_id)
                    if len(image_bytes) > _MAX_SYNC_IMAGE_BYTES:
                        skipped += 1
                    else:
                        outcome = await _ingest_drive_image(
                            user_id=user_id,
                            source_id=file_id,
                            filename=file_name,
                            mime_type=mime_type,
                            image_bytes=image_bytes,
                            db=db,
                        )
                        if outcome == "imported":
                            imported += 1
                        else:
                            skipped += 1
                except Exception as exc:
                    await db.rollback()
                    failed += 1
                    print(f"Drive sync for user {user_id}: failed processing {file_id}: {exc}")
        else:
            try:
                zip_bytes = await _download_drive_file(access_token, file_id)
                entries = extract_image_files_from_zip(zip_bytes, _MAX_SYNC_IMAGE_BYTES)
                if not entries:
                    skipped += 1
                else:
                    pending += max(0, len(entries) - 1)
                    await _update_state_counters(
                        state=state,
                        processed=processed,
                        imported=imported,
                        skipped=skipped,
                        failed=failed,
                        pending=pending,
                        db=db,
                    )
                    for entry_name, entry_bytes, entry_content_type in entries:
                        entry_source_id = f"{file_id}:{entry_name}"
                        if await _source_exists(user_id, entry_source_id, db):
                            skipped += 1
                        else:
                            try:
                                outcome = await _ingest_drive_image(
                                    user_id=user_id,
                                    source_id=entry_source_id,
                                    filename=entry_name,
                                    mime_type=entry_content_type,
                                    image_bytes=entry_bytes,
                                    db=db,
                                )
                                if outcome == "imported":
                                    imported += 1
                                else:
                                    skipped += 1
                            except Exception as exc:
                                await db.rollback()
                                failed += 1
                                print(f"Drive sync for user {user_id}: failed processing zip entry {entry_source_id}: {exc}")

                        processed += 1
                        pending -= 1
                        await _update_state_counters(
                            state=state,
                            processed=processed,
                            imported=imported,
                            skipped=skipped,
                            failed=failed,
                            pending=pending,
                            db=db,
                        )
                    continue
            except Exception as exc:
                await db.rollback()
                failed += 1
                print(f"Drive sync for user {user_id}: failed processing zip {file_id}: {exc}")

        processed += 1
        pending -= 1
        await _update_state_counters(
            state=state,
            processed=processed,
            imported=imported,
            skipped=skipped,
            failed=failed,
            pending=pending,
            db=db,
        )

    state.status = "idle"
    state.last_error = None
    state.last_sync_at = datetime.now(timezone.utc)
    state.pending_count = 0
    await db.commit()


async def _run_sync_task(user_id, user_key: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            await sync_user(user_id, db)
    except Exception as exc:
        async with AsyncSessionLocal() as db:
            state = await _ensure_state(user_id, db)
            state.status = "idle"
            state.last_error = str(exc)
            await db.commit()
    finally:
        _active_sync_tasks.pop(user_key, None)


def start_user_sync_task(user_id) -> bool:
    user_key = str(user_id)
    active_task = _active_sync_tasks.get(user_key)
    if active_task and not active_task.done():
        return False
    _active_sync_tasks[user_key] = asyncio.create_task(_run_sync_task(user_id, user_key))
    return True


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
