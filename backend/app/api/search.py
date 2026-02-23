from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_current_user
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.user import User
from app.services import clip_client
from app.services.storage import generate_presigned_url

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
@limiter.limit("30/minute")
async def search_photos(
    request: Request,
    q: str = Query(...),
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    embedding = await clip_client.embed_text(q.strip())
    if embedding is None:
        raise HTTPException(status_code=503, detail="Search service temporarily unavailable")

    query_vec = "[" + ",".join(str(value) for value in embedding) + "]"
    stmt = text(
        """
        SELECT
            id,
            storage_key,
            thumbnail_key,
            taken_at,
            1 - (embedding <=> CAST(:query_vec AS vector)) AS score
        FROM photos
        WHERE user_id = CAST(:user_id AS uuid)
          AND is_deleted = false
          AND embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:query_vec AS vector)
        LIMIT 20
        """
    )
    result = await db.execute(stmt, {"query_vec": query_vec, "user_id": str(current_user.id)})
    rows = result.mappings().all()

    items = []
    for row in rows:
        items.append(
            {
                "id": str(row["id"]),
                "thumbnail_url": generate_presigned_url(row["thumbnail_key"]) if row["thumbnail_key"] else None,
                "taken_at": row["taken_at"].isoformat() if row["taken_at"] else None,
                "score": float(row["score"]) if row["score"] is not None else 0.0,
            }
        )

    return items
