"""Redis client for chat queue and pubsub"""
from typing import Any
import redis.asyncio as aioredis
from core.config import settings

_redis: Any | None = None


async def get_redis() -> Any:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def close_redis():
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
