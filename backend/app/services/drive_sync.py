from __future__ import annotations

import logging
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.jobs.queue import push_drive_sync_job, push_embedding_job
from app.models.drive import DriveSyncState
from app.models.drive_job import DriveSyncCheckpoint, DriveSyncFile, DriveSyncJob
from app.models.photo import Photo
from app.models.user import OAuthAccount
from app.services.dedup import compute_phash, is_duplicate
from app.services.exif import extract_exif
from app.services.storage import upload_file
from app.services.thumbnail import generate_thumbnail
from app.services.zip_utils import detect_image_content_type, is_zip_upload

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
GOOGLE_DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
DEFAULT_BATCH_SIZE = 50
MAX_BATCH_SIZE = 100
_sync_progress: dict[str, dict[str, Any]] = {}
logger = logging.getLogger(__name__)


def _progress_template() -> dict[str, Any]:
    return {
        "status": "idle",
        "phase": "idle",
        "job_id": None,
        "batch_size": DEFAULT_BATCH_SIZE,
        "current_batch": 0,
        "progress_percent": 0,
        "total_files": 0,
        "processed_files": 0,
        "uploaded": 0,
        "skipped": 0,
        "failed": 0,
        "zip_files_total": 0,
        "zip_files_processed": 0,
        "zip_entries_total": 0,
        "zip_entries_processed": 0,
        "current_item": None,
        "message": "",
        "recent_failures": [],
    }


def _set_progress(user_id: str | UUID, **kwargs) -> None:
    key = str(user_id)
    current = _sync_progress.get(key, _progress_template())
    current.update(kwargs)
    total_files = int(current.get("total_files") or 0)
    processed_files = int(current.get("processed_files") or 0)
    if total_files > 0:
        current["progress_percent"] = min(100, int((processed_files / total_files) * 100))
    elif current.get("status") in {"done", "completed"}:
        current["progress_percent"] = 100
    else:
        current["progress_percent"] = 0
    _sync_progress[key] = current


def _log_job_progress(user_id: str | UUID, event: str) -> None:
    progress = get_sync_progress(user_id)
    logger.info(
        "drive_sync event=%s user_id=%s job_id=%s phase=%s batch=%s processed=%s total=%s uploaded=%s skipped=%s failed=%s percent=%s",
        event,
        user_id,
        progress.get("job_id"),
        progress.get("phase"),
        progress.get("current_batch"),
        progress.get("processed_files"),
        progress.get("total_files"),
        progress.get("uploaded"),
        progress.get("skipped"),
        progress.get("failed"),
        progress.get("progress_percent"),
    )


def _append_failure(user_id: str | UUID, item: str, reason: str) -> None:
    progress = get_sync_progress(user_id)
    recent = list(progress.get("recent_failures", []))
    recent.append({"item": item, "reason": reason})
    if len(recent) > 10:
        recent = recent[-10:]
    _set_progress(user_id, recent_failures=recent)


def get_sync_progress(user_id: str | UUID) -> dict[str, Any]:
    return _sync_progress.get(str(user_id), _progress_template())


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
    return filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp", ".tiff"))


def _looks_like_supported_drive_file(filename: str, mime_type: str) -> bool:
    return _looks_like_image(filename, mime_type) or is_zip_upload(filename, mime_type)


async def _list_drive_children(client: httpx.AsyncClient, headers: dict[str, str], folder_id: str) -> list[dict]:
    files: list[dict] = []
    page_token: str | None = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed=false",
            "fields": "nextPageToken,files(id,name,mimeType,size,trashed)",
            "pageSize": "1000",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        response = await client.get(f"{GOOGLE_DRIVE_API_BASE}/files", headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()
        files.extend(payload.get("files", []))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return files


async def _collect_drive_files(client: httpx.AsyncClient, headers: dict[str, str], root_folder_id: str) -> list[dict]:
    queue = [root_folder_id]
    out: list[dict] = []
    while queue:
        folder_id = queue.pop(0)
        children = await _list_drive_children(client, headers, folder_id)
        for item in children:
            mime_type = item.get("mimeType", "")
            if mime_type == GOOGLE_DRIVE_FOLDER_MIME:
                queue.append(item["id"])
                continue
            if _looks_like_supported_drive_file(item.get("name", ""), mime_type):
                out.append(item)
    return out


async def enqueue_drive_sync_job(
    db: AsyncSession,
    user_id: UUID,
    folder_id: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> DriveSyncJob:
    size = max(1, min(batch_size, MAX_BATCH_SIZE))
    job = DriveSyncJob(
        user_id=user_id,
        folder_id=folder_id,
        status="queued",
        attempts=0,
        max_attempts=5,
        batch_size=size,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    push_drive_sync_job(str(job.id))
    _set_progress(user_id, status="queued", phase="queued", job_id=str(job.id), message="Sync job queued.")
    _log_job_progress(user_id, "queued")
    return job


def start_user_sync_task(user_id: str | UUID) -> bool:
    # Queue-based architecture: push a job id, no in-memory per-user task.
    # API now uses enqueue_drive_sync_job directly and does not call this.
    return False


async def _upsert_sync_file(
    db: AsyncSession,
    job_id: UUID,
    user_id: UUID,
    source_file_id: str,
    source_entry_id: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
) -> DriveSyncFile:
    result = await db.execute(
        select(DriveSyncFile).where(
            DriveSyncFile.user_id == user_id,
            DriveSyncFile.source_file_id == source_file_id,
            DriveSyncFile.source_entry_id == source_entry_id,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        return row
    row = DriveSyncFile(
        job_id=job_id,
        user_id=user_id,
        source_file_id=source_file_id,
        source_entry_id=source_entry_id,
        filename=filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        state="pending",
    )
    db.add(row)
    await db.flush()
    return row


async def _save_batch_photos(
    db: AsyncSession,
    *,
    user_id: UUID,
    batch_no: int,
    items: list[dict[str, Any]],
    counters: dict[str, int],
) -> None:
    photos_to_insert: list[Photo] = []
    completed_sync_rows: list[DriveSyncFile] = []
    latest_success_key: str | None = None

    for item in items:
        source_file_id = item["source_file_id"]
        source_entry_id = item["source_entry_id"]
        filename = item["filename"]
        file_bytes = item["file_bytes"]
        mime_type = item["mime_type"]
        success_key = item["success_key"]

        sync_row = await _upsert_sync_file(
            db,
            job_id=item["job_id"],
            user_id=user_id,
            source_file_id=source_file_id,
            source_entry_id=source_entry_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(file_bytes),
        )
        if sync_row.state == "completed":
            counters["skipped"] += 1
            continue

        try:
            phash_str = compute_phash(file_bytes)
            if await is_duplicate(phash_str, str(user_id), db):
                sync_row.state = "skipped"
                sync_row.batch_no = batch_no
                sync_row.processed_at = datetime.now(timezone.utc)
                counters["skipped"] += 1
                latest_success_key = success_key
                continue

            thumbnail_bytes = generate_thumbnail(file_bytes)
            exif = extract_exif(file_bytes)
            storage_key = f"users/{user_id}/photos/{uuid4()}.jpg"
            thumbnail_key = f"users/{user_id}/thumbnails/{uuid4()}.webp"
            upload_file(file_bytes, storage_key, mime_type)
            upload_file(thumbnail_bytes, thumbnail_key, "image/webp")

            photos_to_insert.append(
                Photo(
                    user_id=user_id,
                    storage_key=storage_key,
                    thumbnail_key=thumbnail_key,
                    original_filename=filename,
                    file_size_bytes=len(file_bytes),
                    mime_type=mime_type,
                    width=exif.get("width"),
                    height=exif.get("height"),
                    taken_at=_parse_taken_at(exif.get("taken_at")),
                    source="google_drive",
                    source_id=source_entry_id if source_entry_id else source_file_id,
                    phash=phash_str,
                    embedding=None,
                    caption=None,
                    gps_lat=exif.get("gps_lat"),
                    gps_lng=exif.get("gps_lng"),
                    camera_make=exif.get("camera_make"),
                    is_deleted=False,
                )
            )
            sync_row.state = "completed"
            sync_row.batch_no = batch_no
            sync_row.processed_at = datetime.now(timezone.utc)
            completed_sync_rows.append(sync_row)
            counters["uploaded"] += 1
            latest_success_key = success_key
        except Exception as exc:
            sync_row.state = "failed"
            sync_row.batch_no = batch_no
            sync_row.error_message = str(exc)
            sync_row.processed_at = datetime.now(timezone.utc)
            counters["failed"] += 1
            _append_failure(user_id, filename, str(exc))
            logger.exception("Drive sync batch item failed user=%s file=%s", user_id, filename)

    if photos_to_insert:
        db.add_all(photos_to_insert)
    await db.flush()

    # Queue embeddings after IDs are generated.
    for photo in photos_to_insert:
        push_embedding_job(str(photo.id))

    checkpoint = await db.get(DriveSyncCheckpoint, items[0]["job_id"])
    if checkpoint is None:
        checkpoint = DriveSyncCheckpoint(job_id=items[0]["job_id"], last_batch_no=batch_no, last_success_key=latest_success_key)
        db.add(checkpoint)
    else:
        checkpoint.last_batch_no = batch_no
        checkpoint.last_success_key = latest_success_key
        checkpoint.updated_at = datetime.now(timezone.utc)


async def _download_drive_file_to_temp(
    client: httpx.AsyncClient, headers: dict[str, str], source_id: str, suffix: str
) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        async with client.stream(
            "GET",
            f"{GOOGLE_DRIVE_API_BASE}/files/{source_id}",
            headers=headers,
            params={"alt": "media"},
        ) as response:
            response.raise_for_status()
            with tmp_path.open("wb") as handle:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                    handle.write(chunk)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
    return tmp_path


def _iter_zip_entries(zip_path: Path):
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir() or info.file_size > MAX_FILE_SIZE_BYTES:
                continue
            entry_bytes = archive.read(info)
            if len(entry_bytes) > MAX_FILE_SIZE_BYTES:
                continue
            entry_mime = detect_image_content_type(info.filename, entry_bytes)
            if not entry_mime or not entry_mime.startswith("image/"):
                continue
            yield {
                "entry_name": info.filename,
                "entry_bytes": entry_bytes,
                "entry_mime": entry_mime,
                "entry_size": len(entry_bytes),
            }


async def process_drive_sync_job(job_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(DriveSyncJob, job_id)
        if job is None:
            return
        if job.status == "completed":
            return

        job.status = "running"
        job.attempts = int(job.attempts or 0) + 1
        job.started_at = datetime.now(timezone.utc)
        job.last_error = None
        await db.commit()

        _set_progress(job.user_id, status="running", phase="auth", job_id=str(job.id), message="Starting sync job...")
        _log_job_progress(job.user_id, "started")

        oauth_result = await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == job.user_id,
                OAuthAccount.provider == "google",
            )
        )
        oauth_account = oauth_result.scalar_one_or_none()
        if oauth_account is None or not oauth_account.refresh_token:
            job.status = "failed"
            job.last_error = "Google refresh token not found."
            await db.commit()
            _set_progress(job.user_id, status="error", phase="idle", message=job.last_error)
            return

        state = await db.get(DriveSyncState, job.user_id)
        if state is None or not state.folder_id:
            job.status = "failed"
            job.last_error = "Drive folder is not selected."
            await db.commit()
            _set_progress(job.user_id, status="error", phase="idle", message=job.last_error)
            return

        try:
            access_token = await refresh_access_token(oauth_account.refresh_token)
        except Exception:
            state.sync_enabled = False
            state.last_error = "Google account disconnected. Please reconnect."
            job.status = "failed"
            job.last_error = state.last_error
            await db.commit()
            _set_progress(job.user_id, status="error", phase="idle", message=state.last_error)
            return

        headers = {"Authorization": f"Bearer {access_token}"}
        counters = {"processed": 0, "uploaded": 0, "skipped": 0, "failed": 0}
        batch_size = max(1, min(int(job.batch_size or DEFAULT_BATCH_SIZE), MAX_BATCH_SIZE))
        batch_no = 0

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                _set_progress(job.user_id, phase="listing", message="Scanning Drive folder...")
                files = await _collect_drive_files(client, headers, job.folder_id)
                zip_count = sum(1 for f in files if is_zip_upload(f.get("name", ""), f.get("mimeType", "")))
                job.total_discovered = len(files)
                await db.commit()
                _set_progress(
                    job.user_id,
                    batch_size=batch_size,
                    total_files=len(files),
                    zip_files_total=zip_count,
                    message=f"Discovered {len(files)} files.",
                )
                _log_job_progress(job.user_id, "discovered")

                pending_batch: list[dict[str, Any]] = []
                for file_data in files:
                    source_file_id = file_data.get("id")
                    file_name = file_data.get("name") or source_file_id or "unknown"
                    mime_type = file_data.get("mimeType") or ""
                    if not source_file_id:
                        counters["failed"] += 1
                        continue

                    if is_zip_upload(file_name, mime_type):
                        _set_progress(job.user_id, phase="extracting", current_item=file_name, message=f"Extracting {file_name}")
                        zip_path: Path | None = None
                        try:
                            zip_path = await _download_drive_file_to_temp(client, headers, source_file_id, ".zip")
                            _set_progress(
                                job.user_id,
                                zip_files_processed=get_sync_progress(job.user_id).get("zip_files_processed", 0) + 1,
                            )
                            for entry in _iter_zip_entries(zip_path):
                                _set_progress(
                                    job.user_id,
                                    zip_entries_total=get_sync_progress(job.user_id).get("zip_entries_total", 0) + 1,
                                    zip_entries_processed=get_sync_progress(job.user_id).get("zip_entries_processed", 0) + 1,
                                )
                                pending_batch.append(
                                    {
                                        "job_id": job.id,
                                        "source_file_id": source_file_id,
                                        "source_entry_id": entry["entry_name"],
                                        "filename": entry["entry_name"],
                                        "mime_type": entry["entry_mime"],
                                        "file_bytes": entry["entry_bytes"],
                                        "success_key": f"{source_file_id}:{entry['entry_name']}",
                                    }
                                )
                                if len(pending_batch) >= batch_size:
                                    batch_no += 1
                                    await _save_batch_photos(db, user_id=job.user_id, batch_no=batch_no, items=pending_batch, counters=counters)
                                    counters["processed"] += len(pending_batch)
                                    pending_batch = []
                                    job.processed_count = counters["processed"]
                                    job.uploaded_count = counters["uploaded"]
                                    job.skipped_count = counters["skipped"]
                                    job.failed_count = counters["failed"]
                                    state.last_sync_at = datetime.now(timezone.utc)
                                    await db.commit()
                                    _set_progress(
                                        job.user_id,
                                        phase="importing",
                                        current_batch=batch_no,
                                        processed_files=counters["processed"],
                                        uploaded=counters["uploaded"],
                                        skipped=counters["skipped"],
                                        failed=counters["failed"],
                                        message=f"Processed batch {batch_no}",
                                    )
                                    _log_job_progress(job.user_id, "batch_committed")
                        except Exception as exc:
                            counters["failed"] += 1
                            _append_failure(job.user_id, file_name, str(exc))
                            logger.exception("ZIP processing failed for user=%s file=%s", job.user_id, file_name)
                        finally:
                            if zip_path and zip_path.exists():
                                zip_path.unlink(missing_ok=True)
                        continue

                    if not _looks_like_image(file_name, mime_type):
                        counters["skipped"] += 1
                        continue

                    _set_progress(job.user_id, phase="importing", current_item=file_name, message=f"Importing {file_name}")
                    response = await client.get(
                        f"{GOOGLE_DRIVE_API_BASE}/files/{source_file_id}",
                        headers=headers,
                        params={"alt": "media"},
                    )
                    response.raise_for_status()
                    file_bytes = response.content
                    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
                        counters["skipped"] += 1
                        continue
                    detected_mime = detect_image_content_type(file_name, file_bytes)
                    if not detected_mime:
                        counters["skipped"] += 1
                        continue

                    pending_batch.append(
                        {
                            "job_id": job.id,
                            "source_file_id": source_file_id,
                            "source_entry_id": "",
                            "filename": file_name,
                            "mime_type": detected_mime,
                            "file_bytes": file_bytes,
                            "success_key": source_file_id,
                        }
                    )
                    if len(pending_batch) >= batch_size:
                        batch_no += 1
                        await _save_batch_photos(db, user_id=job.user_id, batch_no=batch_no, items=pending_batch, counters=counters)
                        counters["processed"] += len(pending_batch)
                        pending_batch = []
                        job.processed_count = counters["processed"]
                        job.uploaded_count = counters["uploaded"]
                        job.skipped_count = counters["skipped"]
                        job.failed_count = counters["failed"]
                        state.last_sync_at = datetime.now(timezone.utc)
                        await db.commit()
                        _set_progress(
                            job.user_id,
                            phase="importing",
                            current_batch=batch_no,
                            processed_files=counters["processed"],
                            uploaded=counters["uploaded"],
                            skipped=counters["skipped"],
                            failed=counters["failed"],
                            message=f"Processed batch {batch_no}",
                        )
                        _log_job_progress(job.user_id, "batch_committed")

                if pending_batch:
                    batch_no += 1
                    await _save_batch_photos(db, user_id=job.user_id, batch_no=batch_no, items=pending_batch, counters=counters)
                    counters["processed"] += len(pending_batch)
                    job.processed_count = counters["processed"]
                    job.uploaded_count = counters["uploaded"]
                    job.skipped_count = counters["skipped"]
                    job.failed_count = counters["failed"]
                    state.last_sync_at = datetime.now(timezone.utc)
                    await db.commit()
                    _set_progress(
                        job.user_id,
                        phase="importing",
                        current_batch=batch_no,
                        processed_files=counters["processed"],
                        uploaded=counters["uploaded"],
                        skipped=counters["skipped"],
                        failed=counters["failed"],
                        message=f"Processed batch {batch_no}",
                    )
                    _log_job_progress(job.user_id, "batch_committed")

            state.last_error = None
            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            _set_progress(
                job.user_id,
                status="done",
                phase="completed",
                current_batch=batch_no,
                processed_files=counters["processed"],
                uploaded=counters["uploaded"],
                skipped=counters["skipped"],
                failed=counters["failed"],
                message=f"Sync completed. Uploaded {counters['uploaded']}, skipped {counters['skipped']}, failed {counters['failed']}.",
            )
            _log_job_progress(job.user_id, "completed")
        except Exception as exc:
            await db.rollback()
            job.status = "failed"
            job.last_error = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()
            if int(job.attempts or 0) < int(job.max_attempts or 5):
                push_drive_sync_job(str(job.id))
            _append_failure(job.user_id, "job", str(exc))
            _set_progress(job.user_id, status="error", phase="idle", message=f"Sync failed: {exc}")
            _log_job_progress(job.user_id, "failed")
            logger.exception("Drive sync job failed job_id=%s", job.id)


async def run_drive_sync_job(job_id_str: str) -> None:
    try:
        job_id = UUID(job_id_str)
    except ValueError:
        return
    await process_drive_sync_job(job_id)


async def sync_all_users() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DriveSyncState).where(
                DriveSyncState.sync_enabled.is_(True),
                DriveSyncState.folder_id.is_not(None),
            )
        )
        states = result.scalars().all()
        for state in states:
            try:
                await enqueue_drive_sync_job(db, state.user_id, state.folder_id)
                logger.info("drive_sync event=scheduled_enqueue user_id=%s folder_id=%s", state.user_id, state.folder_id)
            except Exception:
                logger.exception("Failed to enqueue scheduled sync for user=%s", state.user_id)
