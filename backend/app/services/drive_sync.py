from __future__ import annotations

import logging
import mimetypes
import shutil
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
from app.services.dedup import compute_phash
from app.services.exif import extract_exif
from app.services.storage import upload_file
from app.services.thumbnail import generate_thumbnail
from app.services.zip_utils import detect_image_content_type, is_zip_upload

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
GOOGLE_DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
DRIVE_MAX_FILE_SIZE_BYTES = 512 * 1024 * 1024
MAX_ZIP_CONTAINER_BYTES = 5 * 1024 * 1024 * 1024
DEFAULT_BATCH_SIZE = 50
MAX_BATCH_SIZE = 100
ZIP_COMPLETION_MARKER = "__zip_completed__"
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
        "download_percent": 0,
        "downloaded_mb": 0,
        "download_total_mb": 0,
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
    if processed_files > total_files:
        total_files = processed_files
        current["total_files"] = total_files
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
        "drive_sync event=%s user_id=%s job_id=%s phase=%s batch=%s processed=%s total=%s uploaded=%s skipped=%s failed=%s percent=%s message=%s",
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
        progress.get("message"),
    )
    print(
        "[drive_sync]",
        f"event={event}",
        f"user_id={user_id}",
        f"job_id={progress.get('job_id')}",
        f"phase={progress.get('phase')}",
        f"batch={progress.get('current_batch')}",
        f"processed={progress.get('processed_files')}/{progress.get('total_files')}",
        f"uploaded={progress.get('uploaded')}",
        f"skipped={progress.get('skipped')}",
        f"failed={progress.get('failed')}",
        f"percent={progress.get('progress_percent')}",
        f"message={progress.get('message')}",
        flush=True,
    )


def _append_failure(user_id: str | UUID, item: str, reason: str) -> None:
    progress = get_sync_progress(user_id)
    recent = list(progress.get("recent_failures", []))
    recent.append({"item": item, "reason": reason})
    if len(recent) > 10:
        recent = recent[-10:]
    _set_progress(user_id, recent_failures=recent)


def _increase_total_files(user_id: str | UUID, increment: int = 1) -> int:
    progress = get_sync_progress(user_id)
    total_files = int(progress.get("total_files") or 0) + increment
    _set_progress(user_id, total_files=total_files)
    return total_files


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
    existing_result = await db.execute(
        select(DriveSyncJob)
        .where(
            DriveSyncJob.user_id == user_id,
            DriveSyncJob.folder_id == folder_id,
            DriveSyncJob.status.in_(["queued", "running"]),
        )
        .order_by(DriveSyncJob.created_at.desc())
        .limit(1)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        _set_progress(
            user_id,
            status=existing.status,
            job_id=str(existing.id),
            message="Sync job already active. Reusing existing job.",
        )
        _log_job_progress(user_id, "reuse_active_job")
        return existing

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


async def _is_zip_already_completed(
    db: AsyncSession,
    *,
    user_id: UUID,
    source_file_id: str,
) -> bool:
    result = await db.execute(
        select(DriveSyncFile).where(
            DriveSyncFile.user_id == user_id,
            DriveSyncFile.source_file_id == source_file_id,
            DriveSyncFile.source_entry_id == ZIP_COMPLETION_MARKER,
            DriveSyncFile.state == "completed",
        )
    )
    return result.scalar_one_or_none() is not None


async def _mark_zip_completed(
    db: AsyncSession,
    *,
    job_id: UUID,
    user_id: UUID,
    source_file_id: str,
    filename: str,
) -> None:
    row = await _upsert_sync_file(
        db,
        job_id=job_id,
        user_id=user_id,
        source_file_id=source_file_id,
        source_entry_id=ZIP_COMPLETION_MARKER,
        filename=filename,
        mime_type="application/zip",
        size_bytes=0,
    )
    row.state = "completed"
    row.batch_no = 0
    row.error_message = None
    row.processed_at = datetime.now(timezone.utc)


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
        file_bytes = item.get("file_bytes")
        file_path = item.get("file_path")
        mime_type = item["mime_type"]
        success_key = item["success_key"]
        size_bytes = len(file_bytes) if file_bytes is not None else 0
        if size_bytes == 0 and file_path:
            path_obj = Path(file_path)
            if path_obj.exists():
                size_bytes = path_obj.stat().st_size

        sync_row = await _upsert_sync_file(
            db,
            job_id=item["job_id"],
            user_id=user_id,
            source_file_id=source_file_id,
            source_entry_id=source_entry_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
        )
        if sync_row.state == "completed":
            counters["skipped"] += 1
            if file_path:
                Path(file_path).unlink(missing_ok=True)
            continue
        if file_bytes is None and file_path:
            file_bytes = Path(file_path).read_bytes()
        if file_bytes is None:
            counters["failed"] += 1
            _append_failure(user_id, filename, "Missing file payload")
            if file_path:
                Path(file_path).unlink(missing_ok=True)
            continue
        try:
            phash_str = compute_phash(file_bytes)

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
        finally:
            if file_path:
                Path(file_path).unlink(missing_ok=True)

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
    client: httpx.AsyncClient,
    headers: dict[str, str],
    source_id: str,
    suffix: str,
    *,
    user_id: UUID,
    filename: str,
    expected_size: int | None = None,
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
            total_size = expected_size
            if total_size is None:
                try:
                    content_length = response.headers.get("content-length")
                    total_size = int(content_length) if content_length else None
                except (TypeError, ValueError):
                    total_size = None

            downloaded = 0
            next_report_at = 64 * 1024 * 1024
            with tmp_path.open("wb") as handle:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if downloaded >= next_report_at:
                        if total_size and total_size > 0:
                            percent = min(99, int((downloaded / total_size) * 100))
                            message = (
                                f"Downloading ZIP {filename}: "
                                f"{percent}% ({downloaded // (1024 * 1024)}MB/{total_size // (1024 * 1024)}MB)"
                            )
                        else:
                            message = f"Downloading ZIP {filename}: {downloaded // (1024 * 1024)}MB"
                        _set_progress(
                            user_id,
                            phase="downloading_zip",
                            current_item=filename,
                            download_percent=percent if total_size and total_size > 0 else 0,
                            downloaded_mb=downloaded // (1024 * 1024),
                            download_total_mb=(total_size // (1024 * 1024)) if total_size else 0,
                            message=message,
                        )
                        _log_job_progress(user_id, "zip_download_progress")
                        next_report_at += 64 * 1024 * 1024
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
    return tmp_path


def _extract_zip_images_to_flat_dir(
    archive_path: Path,
    output_dir: Path,
    *,
    prefix: str = "",
    depth: int = 0,
) -> tuple[int, int, int, list[dict[str, Any]]]:
    if depth > 3:
        return (0, 0, 0, [])

    total_entries = 0
    candidate_entries = 0
    accepted_entries = 0
    extracted: list[dict[str, Any]] = []

    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            total_entries += 1
            entry_name = f"{prefix}{info.filename}"
            guessed_type, _ = mimetypes.guess_type(info.filename)

            if is_zip_upload(info.filename, guessed_type):
                if info.file_size > MAX_ZIP_CONTAINER_BYTES:
                    continue
                nested_tmp_path: Path | None = None
                try:
                    with archive.open(info, "r") as source_stream:
                        nested_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                        nested_tmp_path = Path(nested_tmp.name)
                        with nested_tmp:
                            shutil.copyfileobj(source_stream, nested_tmp, length=1024 * 1024)
                    n_total, n_candidates, n_accepted, n_extracted = _extract_zip_images_to_flat_dir(
                        nested_tmp_path,
                        output_dir,
                        prefix=f"{entry_name}::",
                        depth=depth + 1,
                    )
                    total_entries += n_total
                    candidate_entries += n_candidates
                    accepted_entries += n_accepted
                    extracted.extend(n_extracted)
                except zipfile.BadZipFile:
                    continue
                finally:
                    if nested_tmp_path and nested_tmp_path.exists():
                        nested_tmp_path.unlink(missing_ok=True)
                continue

            if (guessed_type and guessed_type.startswith("image/")) or info.filename.lower().endswith(
                (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif", ".bmp", ".tiff")
            ):
                candidate_entries += 1

            if info.file_size > DRIVE_MAX_FILE_SIZE_BYTES:
                continue

            with archive.open(info, "r") as source_stream:
                entry_bytes = source_stream.read(DRIVE_MAX_FILE_SIZE_BYTES + 1)
            if len(entry_bytes) > DRIVE_MAX_FILE_SIZE_BYTES:
                continue

            entry_mime = detect_image_content_type(info.filename, entry_bytes)
            if not entry_mime or not entry_mime.startswith("image/"):
                continue

            accepted_entries += 1
            suffix = Path(info.filename).suffix or ".bin"
            extracted_path = output_dir / f"{uuid4().hex}{suffix}"
            extracted_path.write_bytes(entry_bytes)
            extracted.append(
                {
                    "entry_name": entry_name,
                    "entry_mime": entry_mime,
                    "entry_size": len(entry_bytes),
                    "entry_path": str(extracted_path),
                }
            )

    return (total_entries, candidate_entries, accepted_entries, extracted)


async def process_drive_sync_job(job_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(DriveSyncJob, job_id)
        if job is None:
            return
        if job.status == "completed":
            return
        if job.status not in {"queued", "failed"}:
            return

        job.status = "running"
        job.attempts = int(job.attempts or 0) + 1
        job.started_at = datetime.now(timezone.utc)
        job.last_error = None
        await db.commit()

        _set_progress(job.user_id, status="running", phase="auth", job_id=str(job.id), message="Starting sync job...")
        _set_progress(
            job.user_id,
            current_batch=0,
            total_files=0,
            processed_files=0,
            uploaded=0,
            skipped=0,
            failed=0,
            zip_entries_total=0,
            zip_entries_processed=0,
            current_item=None,
        )
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
                discovered_units = 0
                job.total_discovered = 0
                await db.commit()
                _set_progress(
                    job.user_id,
                    batch_size=batch_size,
                    total_files=0,
                    zip_files_total=zip_count,
                    message=f"Discovered {len(files)} source files. Scanning entries...",
                )
                _log_job_progress(job.user_id, "discovered")

                pending_batch: list[dict[str, Any]] = []

                async def commit_pending_batch(message: str) -> None:
                    nonlocal batch_no, pending_batch
                    if not pending_batch:
                        return
                    batch_no += 1
                    await _save_batch_photos(
                        db,
                        user_id=job.user_id,
                        batch_no=batch_no,
                        items=pending_batch,
                        counters=counters,
                    )
                    counters["processed"] += len(pending_batch)
                    pending_batch = []
                    job.total_discovered = discovered_units
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
                        message=message,
                    )
                    _log_job_progress(job.user_id, "batch_committed")

                for file_data in files:
                    source_file_id = file_data.get("id")
                    file_name = file_data.get("name") or source_file_id or "unknown"
                    mime_type = file_data.get("mimeType") or ""
                    if not source_file_id:
                        counters["failed"] += 1
                        continue

                    if is_zip_upload(file_name, mime_type):
                        if await _is_zip_already_completed(
                            db,
                            user_id=job.user_id,
                            source_file_id=source_file_id,
                        ):
                            counters["skipped"] += 1
                            _set_progress(
                                job.user_id,
                                phase="importing",
                                current_item=file_name,
                                message=f"Skipping already completed ZIP {file_name}",
                            )
                            _log_job_progress(job.user_id, "zip_skipped_completed")
                            continue
                        # Strict sequential ZIP mode:
                        # finish pending work before starting a new ZIP.
                        await commit_pending_batch("Processed pre-ZIP batch")
                        _set_progress(
                            job.user_id,
                            phase="downloading_zip",
                            current_item=file_name,
                            download_percent=0,
                            downloaded_mb=0,
                            download_total_mb=0,
                            message=f"Downloading {file_name}",
                        )
                        _log_job_progress(job.user_id, "zip_download_started")
                        zip_path: Path | None = None
                        extract_dir: Path | None = None
                        try:
                            expected_size = None
                            try:
                                if file_data.get("size") is not None:
                                    expected_size = int(file_data.get("size"))
                            except (TypeError, ValueError):
                                expected_size = None
                            zip_path = await _download_drive_file_to_temp(
                                client,
                                headers,
                                source_file_id,
                                ".zip",
                                user_id=job.user_id,
                                filename=file_name,
                                expected_size=expected_size,
                            )
                            _set_progress(job.user_id, phase="extracting", current_item=file_name, message=f"Extracting {file_name}")
                            _log_job_progress(job.user_id, "zip_extract_started")
                            _set_progress(
                                job.user_id,
                                zip_files_processed=get_sync_progress(job.user_id).get("zip_files_processed", 0) + 1,
                            )
                            extract_dir = Path(tempfile.mkdtemp(prefix="drive_extract_"))
                            total_entries = 0
                            candidate_entries = 0
                            accepted_entries = 0
                            extracted_entries: list[dict[str, Any]] = []
                            total_entries, candidate_entries, accepted_entries, extracted_entries = (
                                _extract_zip_images_to_flat_dir(zip_path, extract_dir)
                            )
                            discovered_units += accepted_entries
                            if accepted_entries > 0:
                                _increase_total_files(job.user_id, accepted_entries)
                            _set_progress(
                                job.user_id,
                                zip_entries_total=get_sync_progress(job.user_id).get("zip_entries_total", 0)
                                + candidate_entries,
                                zip_entries_processed=get_sync_progress(job.user_id).get("zip_entries_processed", 0)
                                + accepted_entries,
                            )
                            for entry in extracted_entries:
                                pending_batch.append(
                                    {
                                        "job_id": job.id,
                                        "source_file_id": source_file_id,
                                        "source_entry_id": entry["entry_name"],
                                        "filename": entry["entry_name"],
                                        "mime_type": entry["entry_mime"],
                                        "file_path": entry["entry_path"],
                                        "success_key": f"{source_file_id}:{entry['entry_name']}",
                                    }
                                )
                                if len(pending_batch) >= batch_size:
                                    await commit_pending_batch(f"Processed batch {batch_no + 1}")

                            # Ensure current ZIP is fully committed before moving to next ZIP.
                            await commit_pending_batch(f"Completed ZIP {file_name}")
                            if accepted_entries == 0:
                                counters["failed"] += 1
                                _append_failure(
                                    job.user_id,
                                    file_name,
                                    f"ZIP had no supported/decodeable images (entries={total_entries}, candidates={candidate_entries}).",
                                )
                            _set_progress(
                                job.user_id,
                                skipped=counters["skipped"],
                                download_percent=100,
                                message=(
                                    f"Finished ZIP {file_name} "
                                    f"(entries={total_entries}, candidates={candidate_entries}, accepted={accepted_entries})"
                                ),
                            )
                            _set_progress(
                                job.user_id,
                                phase="extracting",
                                current_item=file_name,
                                message=(
                                    f"Finished ZIP {file_name} "
                                    f"(entries={total_entries}, candidates={candidate_entries}, accepted={accepted_entries})"
                                ),
                            )
                            await _mark_zip_completed(
                                db,
                                job_id=job.id,
                                user_id=job.user_id,
                                source_file_id=source_file_id,
                                filename=file_name,
                            )
                            await db.commit()
                            _log_job_progress(job.user_id, "zip_completed")
                        except Exception as exc:
                            counters["failed"] += 1
                            _append_failure(job.user_id, file_name, str(exc))
                            logger.exception("ZIP processing failed for user=%s file=%s", job.user_id, file_name)
                        finally:
                            if extract_dir and extract_dir.exists():
                                shutil.rmtree(extract_dir, ignore_errors=True)
                            if zip_path and zip_path.exists():
                                zip_path.unlink(missing_ok=True)
                        continue

                    if not _looks_like_image(file_name, mime_type):
                        counters["failed"] += 1
                        _append_failure(job.user_id, file_name, "Unsupported mime type")
                        continue

                    _set_progress(job.user_id, phase="importing", current_item=file_name, message=f"Importing {file_name}")
                    response = await client.get(
                        f"{GOOGLE_DRIVE_API_BASE}/files/{source_file_id}",
                        headers=headers,
                        params={"alt": "media"},
                    )
                    response.raise_for_status()
                    file_bytes = response.content
                    if len(file_bytes) > DRIVE_MAX_FILE_SIZE_BYTES:
                        counters["failed"] += 1
                        _append_failure(job.user_id, file_name, "File exceeds max size")
                        continue
                    detected_mime = detect_image_content_type(file_name, file_bytes)
                    if not detected_mime:
                        counters["failed"] += 1
                        _append_failure(job.user_id, file_name, "Unable to detect image mime")
                        continue

                    discovered_units += 1
                    _increase_total_files(job.user_id, 1)
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
                        await commit_pending_batch(f"Processed batch {batch_no + 1}")

                await commit_pending_batch("Processed final batch")

            state.last_error = None
            job.total_discovered = discovered_units
            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)
            await db.execute(
                DriveSyncJob.__table__.update()
                .where(
                    DriveSyncJob.user_id == job.user_id,
                    DriveSyncJob.folder_id == job.folder_id,
                    DriveSyncJob.id != job.id,
                    DriveSyncJob.status.in_(["queued", "running", "failed"]),
                )
                .values(
                    status="cancelled",
                    last_error="Superseded by latest completed sync job.",
                    finished_at=datetime.now(timezone.utc),
                )
            )
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
