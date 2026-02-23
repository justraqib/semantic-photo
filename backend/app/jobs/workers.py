from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import extract, select

from app.core.database import AsyncSessionLocal
from app.jobs.queue import pop_embedding_job, push_embedding_job
from app.models.photo import Photo
from app.services import clip_client, storage


async def run_embedding_worker() -> None:
    while True:
        photo_id = await asyncio.to_thread(pop_embedding_job)
        if photo_id is None:
            continue

        try:
            photo_uuid = UUID(photo_id)
        except ValueError:
            continue

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Photo).where(Photo.id == photo_uuid))
            photo = result.scalar_one_or_none()
            if photo is None:
                continue

            if photo.embedding:
                continue

            try:
                image_bytes = await asyncio.to_thread(storage.get_file, photo.storage_key)
            except Exception:
                await asyncio.to_thread(push_embedding_job, str(photo.id))
                await asyncio.sleep(60)
                continue

            embedding = await clip_client.embed_image(image_bytes)
            if embedding is None:
                await asyncio.to_thread(push_embedding_job, str(photo.id))
                await asyncio.sleep(60)
                continue

            photo.embedding = json.dumps(embedding)
            photo.embedding_generated_at = datetime.now(timezone.utc)
            await db.commit()
            print(f"Embedded photo {photo.id} successfully")


async def run_daily_memories_job() -> None:
    now = datetime.now(timezone.utc)
    current_month = now.month
    current_day = now.day
    cutoff = datetime(now.year - 1, now.month, now.day, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Photo.user_id, Photo.id)
            .where(
                Photo.taken_at.is_not(None),
                Photo.is_deleted.is_(False),
                Photo.taken_at < cutoff,
                extract("month", Photo.taken_at) == current_month,
                extract("day", Photo.taken_at) == current_day,
            )
            .order_by(Photo.user_id.asc(), Photo.taken_at.desc())
        )
        rows = result.all()

    per_user: dict[str, list[str]] = {}
    for user_id, photo_id in rows:
        key = str(user_id)
        if key not in per_user:
            per_user[key] = []
        if len(per_user[key]) < 10:
            per_user[key].append(str(photo_id))

    print(f"Daily memories candidates generated for {len(per_user)} users")
