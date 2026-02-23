from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_current_user
from app.core.database import get_db
from app.models.drive import DriveSyncState
from app.models.user import User

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncFolderPayload(BaseModel):
    folder_id: str
    folder_name: str


@router.post("/folder")
async def choose_sync_folder(
    payload: SyncFolderPayload,
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DriveSyncState).where(DriveSyncState.user_id == current_user.id))
    state = result.scalar_one_or_none()
    if state is None:
        state = DriveSyncState(user_id=current_user.id)
        db.add(state)

    state.folder_id = payload.folder_id
    state.folder_name = payload.folder_name
    state.sync_enabled = True

    await db.commit()
    await db.refresh(state)
    return {
        "user_id": str(state.user_id),
        "folder_id": state.folder_id,
        "folder_name": state.folder_name,
        "sync_enabled": state.sync_enabled,
        "last_sync_at": state.last_sync_at.isoformat() if state.last_sync_at else None,
        "last_error": state.last_error,
    }


@router.post("/connect")
async def connect_sync(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DriveSyncState).where(DriveSyncState.user_id == current_user.id))
    state = result.scalar_one_or_none()
    if state is None:
        state = DriveSyncState(user_id=current_user.id, sync_enabled=True)
        db.add(state)
    else:
        state.sync_enabled = True

    await db.commit()
    await db.refresh(state)
    return {
        "user_id": str(state.user_id),
        "folder_id": state.folder_id,
        "folder_name": state.folder_name,
        "sync_enabled": state.sync_enabled,
        "last_sync_at": state.last_sync_at.isoformat() if state.last_sync_at else None,
        "last_error": state.last_error,
    }


@router.get("/status")
async def get_sync_status(
    current_user: User = Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DriveSyncState).where(DriveSyncState.user_id == current_user.id))
    state = result.scalar_one_or_none()

    if state is None:
        return {
            "connected": False,
            "folder_name": None,
            "last_sync_at": None,
            "sync_enabled": False,
            "status": "idle",
            "last_error": None,
        }

    return {
        "connected": bool(state.folder_id),
        "folder_name": state.folder_name,
        "last_sync_at": state.last_sync_at.isoformat() if state.last_sync_at else None,
        "sync_enabled": state.sync_enabled,
        "status": "idle",
        "last_error": state.last_error,
    }
