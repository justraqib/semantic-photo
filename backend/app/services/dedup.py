from __future__ import annotations

from io import BytesIO

import imagehash
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def compute_phash(image_bytes: bytes) -> str:
    with Image.open(BytesIO(image_bytes)) as image:
        return str(imagehash.phash(image))


async def is_duplicate(phash_str: str, user_id: str, db: AsyncSession) -> bool:
    query = text("SELECT 1 FROM photos WHERE user_id = :user_id AND phash = :phash LIMIT 1")
    result = await db.execute(query, {"user_id": user_id, "phash": phash_str})
    return result.first() is not None
