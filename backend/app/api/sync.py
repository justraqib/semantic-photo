from pydantic import BaseModel
from fastapi import APIRouter, Depends

from app.api.auth import require_current_user
from app.models.user import User

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncFolderPayload(BaseModel):
    folder_id: str
    folder_name: str


@router.post("/folder")
async def choose_sync_folder(
    payload: SyncFolderPayload,
    current_user: User = Depends(require_current_user),
):
    _ = current_user
    return {"ok": True, "folder_id": payload.folder_id, "folder_name": payload.folder_name}
