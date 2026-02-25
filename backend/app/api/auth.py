import base64
import ipaddress
import json
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token, hash_token
from app.services.auth_service import get_or_create_user, create_refresh_token_for_user, get_current_user
from sqlalchemy import select
from app.models.drive import DriveSyncState
from app.models.user import OAuthAccount, RefreshToken, User

router = APIRouter(prefix="/auth", tags=["auth"])
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_USER_EMAILS_URL = "https://api.github.com/user/emails"


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


def _strip_trailing_slash(url: str) -> str:
    return url.rstrip("/")


def _request_origin(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return _strip_trailing_slash(f"{proto}://{host}")


def _allowed_frontend_origins() -> set[str]:
    origins = {_strip_trailing_slash(settings.FRONTEND_URL)}
    if settings.FRONTEND_URLS:
        extra = [item.strip() for item in settings.FRONTEND_URLS.split(",") if item.strip()]
        origins.update(_strip_trailing_slash(item) for item in extra)
    return origins


def _choose_frontend_origin(request: Request, frontend_origin: str | None) -> str:
    origin = _strip_trailing_slash(frontend_origin) if frontend_origin else _strip_trailing_slash(settings.FRONTEND_URL)
    if origin not in _allowed_frontend_origins() and not _is_private_local_origin(origin):
        raise HTTPException(status_code=400, detail=f"Unsupported frontend origin: {origin}")
    return origin


def _encode_oauth_state(payload: dict[str, str]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _decode_oauth_state(state: str | None) -> dict[str, str]:
    if not state:
        return {}
    try:
        decoded = base64.urlsafe_b64decode(state.encode("utf-8"))
        data = json.loads(decoded.decode("utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def _is_private_local_origin(url: str) -> bool:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname in {"localhost", "127.0.0.1"}:
            return True
        ip = ipaddress.ip_address(hostname)
        return ip.is_private
    except Exception:
        return False


def _private_ip_from_origin(url: str) -> str | None:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return None
        ip = ipaddress.ip_address(hostname)
        if ip.is_private:
            return str(ip)
    except Exception:
        return None
    return None


def _choose_backend_origin(request: Request, backend_origin: str | None = None) -> str:
    configured = _strip_trailing_slash(settings.BACKEND_URL)
    candidate = _strip_trailing_slash(backend_origin) if backend_origin else _request_origin(request)
    if candidate == configured or _is_private_local_origin(candidate):
        return candidate
    return configured

@router.get("/google")
@router.get("/google/login")
async def google_login(request: Request, frontend_origin: str | None = None):
    scope = " ".join(
        [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
    )
    selected_frontend_origin = _choose_frontend_origin(request, frontend_origin)
    backend_origin = _choose_backend_origin(request)
    redirect_uri = f"{backend_origin}/auth/google/callback"
    state = _encode_oauth_state(
        {
            "frontend_origin": selected_frontend_origin,
            "backend_origin": backend_origin,
        }
    )
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    private_ip = _private_ip_from_origin(backend_origin)
    if private_ip:
        params["device_id"] = private_ip
        params["device_name"] = "SemanticPhoto-LAN"
    query = urlencode(params)
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{query}")

@router.get("/google/callback")
async def google_callback(code: str, request: Request, response: Response, state: str | None = None, db: AsyncSession = Depends(get_db)):
    state_data = _decode_oauth_state(state)
    backend_origin = _choose_backend_origin(request, state_data.get("backend_origin"))
    frontend_origin = _strip_trailing_slash(state_data.get("frontend_origin", "")) or _strip_trailing_slash(settings.FRONTEND_URL)
    if frontend_origin not in _allowed_frontend_origins() and not _is_private_local_origin(frontend_origin):
        frontend_origin = _strip_trailing_slash(settings.FRONTEND_URL)

    async with httpx.AsyncClient() as client:
        token_response = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": f"{backend_origin}/auth/google/callback",
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
    provider_user_id = str(google_user["sub"])

    oauth_result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_user_id == provider_user_id,
        )
    )
    oauth_account = oauth_result.scalar_one_or_none()
    if oauth_account is not None:
        oauth_account.access_token = token_data.get("access_token")
        if token_data.get("refresh_token"):
            oauth_account.refresh_token = token_data.get("refresh_token")

    state_result = await db.execute(select(DriveSyncState).where(DriveSyncState.user_id == user.id))
    sync_state = state_result.scalar_one_or_none()
    if sync_state is None:
        db.add(DriveSyncState(user_id=user.id, sync_enabled=True))

    await db.commit()

    access_token = create_access_token(str(user.id))
    raw_refresh_token = await create_refresh_token_for_user(db, user.id)

    redirect = RedirectResponse(url=f"{frontend_origin}/auth/success")
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


@router.get("/github")
async def github_login(request: Request, frontend_origin: str | None = None):
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub OAuth is not configured")

    selected_frontend_origin = _choose_frontend_origin(request, frontend_origin)
    backend_origin = _choose_backend_origin(request)
    redirect_uri = f"{backend_origin}/auth/github/callback"
    state = _encode_oauth_state(
        {
            "frontend_origin": selected_frontend_origin,
            "backend_origin": backend_origin,
        }
    )
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "read:user user:email",
        "state": state,
    }
    return RedirectResponse(f"{GITHUB_AUTH_URL}?{urlencode(params)}")


@router.get("/github/callback")
async def github_callback(
    code: str,
    request: Request,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub OAuth is not configured")

    state_data = _decode_oauth_state(state)
    backend_origin = _choose_backend_origin(request, state_data.get("backend_origin"))
    frontend_origin = _strip_trailing_slash(state_data.get("frontend_origin", "")) or _strip_trailing_slash(settings.FRONTEND_URL)
    if frontend_origin not in _allowed_frontend_origins() and not _is_private_local_origin(frontend_origin):
        frontend_origin = _strip_trailing_slash(settings.FRONTEND_URL)

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": f"{backend_origin}/auth/github/callback",
            },
            headers={"Accept": "application/json"},
        )

    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code with GitHub")
    token_data = token_response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="GitHub token response missing access_token")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient() as client:
        user_response = await client.get(GITHUB_USER_URL, headers=headers)
        emails_response = await client.get(GITHUB_USER_EMAILS_URL, headers=headers)

    if user_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch GitHub user profile")
    github_user = user_response.json()

    email = github_user.get("email")
    if not email and emails_response.status_code == 200:
        for item in emails_response.json():
            if item.get("primary") and item.get("verified") and item.get("email"):
                email = item["email"]
                break
        if not email:
            for item in emails_response.json():
                if item.get("email"):
                    email = item["email"]
                    break
    if not email:
        raise HTTPException(status_code=400, detail="Unable to resolve GitHub account email")

    provider_user_id = str(github_user["id"])
    oauth_result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == "github",
            OAuthAccount.provider_user_id == provider_user_id,
        )
    )
    oauth_account = oauth_result.scalar_one_or_none()

    if oauth_account is not None:
        user_result = await db.execute(select(User).where(User.id == oauth_account.user_id))
        user = user_result.scalar_one()
        user.display_name = github_user.get("name") or github_user.get("login") or user.display_name
        user.avatar_url = github_user.get("avatar_url") or user.avatar_url
        oauth_account.access_token = access_token
    else:
        user_result = await db.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                display_name=github_user.get("name") or github_user.get("login"),
                avatar_url=github_user.get("avatar_url"),
            )
            db.add(user)
            await db.flush()

        db.add(
            OAuthAccount(
                user_id=user.id,
                provider="github",
                provider_user_id=provider_user_id,
                access_token=access_token,
            )
        )

    await db.commit()

    app_access_token = create_access_token(str(user.id))
    raw_refresh_token = await create_refresh_token_for_user(db, user.id)

    redirect = RedirectResponse(url=f"{frontend_origin}/gallery")
    redirect.set_cookie("access_token", app_access_token, httponly=True, samesite="lax", max_age=900)
    redirect.set_cookie("refresh_token", raw_refresh_token, httponly=True, samesite="lax", max_age=86400*30)
    return redirect
