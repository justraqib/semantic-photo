from __future__ import annotations

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

_QUEUE_NAME = "embedding_jobs"
_redis_client: Redis | None = None


def _get_redis_client() -> Redis | None:
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    if not settings.REDIS_URL:
        return None

    _redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def push_embedding_job(photo_id: str) -> None:
    client = _get_redis_client()
    if client is None:
        return

    try:
        client.rpush(_QUEUE_NAME, photo_id)
    except RedisError:
        return


def pop_embedding_job() -> str | None:
    client = _get_redis_client()
    if client is None:
        return None

    try:
        result = client.blpop(_QUEUE_NAME, timeout=1)
    except RedisError:
        return None

    if not result:
        return None

    _, photo_id = result
    return photo_id


def get_embedding_queue_length() -> int:
    client = _get_redis_client()
    if client is None:
        return 0

    try:
        length = client.llen(_QUEUE_NAME)
        return int(length) if length is not None else 0
    except RedisError:
        return 0
