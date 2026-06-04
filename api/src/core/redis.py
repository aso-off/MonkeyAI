import redis.asyncio as aioredis

from core.config import settings
from core.logger import logger

_redis: aioredis.Redis | None = None
_redis_binary: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis, _redis_binary
    _redis = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=20,
    )
    _redis_binary = aioredis.from_url(
        settings.redis_url,
        decode_responses=False,
        max_connections=5,
    )
    logger.info("Redis pool created")


async def close_redis() -> None:
    global _redis, _redis_binary
    if _redis is not None:
        await _redis.aclose()
        _redis = None
    if _redis_binary is not None:
        await _redis_binary.aclose()
        _redis_binary = None
    logger.info("Redis closed")


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis pool is not initialized")
    return _redis


def get_redis_binary() -> aioredis.Redis:
    """Return a binary-mode Redis client (decode_responses=False) for raw bytes."""
    if _redis_binary is None:
        raise RuntimeError("Redis binary pool is not initialized")
    return _redis_binary
