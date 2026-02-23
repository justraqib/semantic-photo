from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from urllib.parse import urlencode
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token, hash_token
from app.services.auth_service import get_or_create_user, create_refresh_token_for_user, get_current_user
from sqlalchemy import select
from app.models.user import RefreshToken, User
from datetime import datetime, timezone

router = APIRouter(prefix="/auth", tags=["auth"])
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


async def require_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await get_current_user(db, payload["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user

@router.get("/google")
@router.get("/google/login")
async def google_login():
    scope = " ".join(
        [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
    )
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": f"{settings.BACKEND_URL}/auth/google/callback",
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent"
    }
    query = urlencode(params)
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{query}")

@router.get("/google/callback")
async def google_callback(code: str, response: Response, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        token_response = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": f"{settings.BACKEND_URL}/auth/google/callback",
            "grant_type": "authorization_code"
        })
    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code with Google")
    token_data = token_response.json()

    async with httpx.AsyncClient() as client:
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"}
        )
    if userinfo_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get user info from Google")
    google_user = userinfo_response.json()

    user = await get_or_create_user(db, google_user)
    access_token = create_access_token(str(user.id))
    raw_refresh_token = await create_refresh_token_for_user(db, user.id)

    redirect = RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/success")
    redirect.set_cookie("access_token", access_token, httponly=True, samesite="lax", max_age=900)
    redirect.set_cookie("refresh_token", raw_refresh_token, httponly=True, samesite="lax", max_age=86400*30)
    return redirect

@router.post("/refresh")
async def refresh_token(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    token_hash = hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc)
        )
    )
    db_token = result.scalar_one_or_none()
    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    new_access_token = create_access_token(str(db_token.user_id))
    response.set_cookie("access_token", new_access_token, httponly=True, samesite="lax", max_age=900)
    return {"message": "Token refreshed"}

@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        token_hash = hash_token(raw_token)
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        db_token = result.scalar_one_or_none()
        if db_token:
            db_token.revoked = True
            await db.commit()
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out"}

@router.get("/me")
async def get_me(user: User = Depends(require_current_user)):
    return {"id": str(user.id), "email": user.email, "display_name": user.display_name, "avatar_url": user.avatar_url}
