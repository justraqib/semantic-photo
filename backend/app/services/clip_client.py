from __future__ import annotations

import httpx

from app.core.config import settings

_TIMEOUT_SECONDS = 10.0
_EXPECTED_EMBEDDING_SIZE = 512


def _base_url() -> str | None:
    if not settings.CLIP_SERVICE_URL:
        return None
    return settings.CLIP_SERVICE_URL.rstrip("/")


def _extract_embedding(payload: dict) -> list[float] | None:
    embedding = payload.get("embedding")
    if not isinstance(embedding, list) or len(embedding) != _EXPECTED_EMBEDDING_SIZE:
        return None
    try:
        return [float(value) for value in embedding]
    except (TypeError, ValueError):
        return None


async def embed_text(query: str) -> list[float] | None:
    base_url = _base_url()
    if not base_url:
        return None

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{base_url}/embed/text",
                json={"text": query},
            )
            response.raise_for_status()
            return _extract_embedding(response.json())
    except (httpx.HTTPError, ValueError, TypeError):
        return None


async def embed_image(image_bytes: bytes) -> list[float] | None:
    base_url = _base_url()
    if not base_url:
        return None

    files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{base_url}/embed/image",
                files=files,
            )
            response.raise_for_status()
            return _extract_embedding(response.json())
    except (httpx.HTTPError, ValueError, TypeError):
        return None
