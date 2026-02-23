from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.auth import require_current_user
from app.core.rate_limit import limiter
from app.models.user import User

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
@limiter.limit("30/minute")
async def search_photos(
    request: Request,
    q: str = Query(...),
    current_user: User = Depends(require_current_user),
):
    _ = current_user
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    return []
