from __future__ import annotations

import httpx
from datetime import datetime
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.jobs.queue import push_embedding_job
from app.models.photo import Photo
from app.models.drive import DriveSyncState
from app.models.user import OAuthAccount
from app.services.dedup import compute_phash, is_duplicate
from app.services.exif import extract_exif
from app.services.storage import upload_file
from app.services.thumbnail import generate_thumbnail

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"


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


async def sync_user(user_id, db: AsyncSession) -> None:
    oauth_result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user_id,
            OAuthAccount.provider == "google",
        )
    )
    oauth_account = oauth_result.scalar_one_or_none()
    if oauth_account is None or not oauth_account.refresh_token:
        raise RuntimeError("Google refresh token not found for user")

    access_token = await refresh_access_token(oauth_account.refresh_token)

    state_result = await db.execute(select(DriveSyncState).where(DriveSyncState.user_id == user_id))
    state = state_result.scalar_one_or_none()
    if state is None:
        state = DriveSyncState(user_id=user_id, sync_enabled=True)
        db.add(state)
        await db.flush()

    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        page_token = state.next_page_token
        if not page_token:
            start_token_response = await client.get(
                f"{GOOGLE_DRIVE_API_BASE}/changes/startPageToken",
                headers=headers,
            )
            start_token_response.raise_for_status()
            page_token = start_token_response.json().get("startPageToken")
            state.next_page_token = page_token
            await db.commit()

        if not page_token:
            raise RuntimeError("Google Drive startPageToken missing")

        changes_response = await client.get(
            f"{GOOGLE_DRIVE_API_BASE}/changes",
            headers=headers,
            params={
                "pageToken": page_token,
                "spaces": "drive",
                "includeRemoved": "true",
                "fields": "changes(fileId,removed,file(id,name,mimeType,trashed,modifiedTime)),nextPageToken,newStartPageToken",
            },
        )
        changes_response.raise_for_status()
        payload = changes_response.json()

    changes = payload.get("changes", [])
    print(f"Drive sync for user {user_id}: received {len(changes)} changes")

    filtered_changes: list[dict] = []
    for change in changes:
        file_data = change.get("file") or {}
        if change.get("removed") is True:
            continue
        if file_data.get("trashed") is True:
            continue
        mime_type = file_data.get("mimeType") or ""
        if not mime_type.startswith("image/"):
            continue
        source_id = file_data.get("id") or change.get("fileId")
        if not source_id:
            continue

        existing_photo_result = await db.execute(
            select(Photo.id).where(
                Photo.user_id == user_id,
                Photo.source == "google_drive",
                Photo.source_id == source_id,
            )
        )
        if existing_photo_result.scalar_one_or_none():
            continue

        filtered_changes.append(change)

    print(f"Drive sync for user {user_id}: {len(filtered_changes)} changes passed filtering")

    async with httpx.AsyncClient(timeout=60.0) as download_client:
        for change in filtered_changes:
            file_data = change.get("file") or {}
            source_id = file_data.get("id") or change.get("fileId")
            mime_type = file_data.get("mimeType") or "image/jpeg"
            file_name = file_data.get("name") or f"{source_id}.jpg"

            try:
                file_response = await download_client.get(
                    f"{GOOGLE_DRIVE_API_BASE}/files/{source_id}",
                    headers=headers,
                    params={"alt": "media"},
                )
                file_response.raise_for_status()
                file_bytes = file_response.content
            except Exception as exc:
                print(f"Drive sync for user {user_id}: failed downloading file {source_id}: {exc}")
                continue

            try:
                phash_str = compute_phash(file_bytes)
                if await is_duplicate(phash_str, str(user_id), db):
                    print(f"Drive sync for user {user_id}: duplicate file skipped {source_id}")
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
                print(f"Drive sync for user {user_id}: imported file {source_id} successfully")
            except Exception as exc:
                print(f"Drive sync for user {user_id}: failed processing file {source_id}: {exc}")
                continue

    state.next_page_token = payload.get("nextPageToken") or payload.get("newStartPageToken") or state.next_page_token
    await db.commit()
