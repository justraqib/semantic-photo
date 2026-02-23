from __future__ import annotations

import httpx

from app.core.config import settings

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


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
