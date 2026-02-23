from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.security import decode_access_token


def user_rate_limit_key(request: Request) -> str:
    token = request.cookies.get("access_token")
    if token:
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            return f"user:{payload['sub']}"
    return f"anon:{get_remote_address(request)}"


limiter = Limiter(key_func=user_rate_limit_key)
