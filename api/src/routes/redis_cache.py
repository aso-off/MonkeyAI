"""
Simple Redis key-value proxy endpoints.
Lets external services (e.g. the bot) read/write shared Redis keys
without having a direct Redis connection, using the API service as a gateway.
"""
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.config import settings
from core.security import verify_service_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/redis", tags=["redis"])


def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


class RedisSetBody(BaseModel):
    value: str
    ttl: int | None = None  # seconds


@router.get("/{key}")
async def redis_get(
    key: str,
    _: None = Depends(verify_service_token),
) -> dict:
    """Read a Redis key. Returns null if not found."""
    r = _get_redis()
    try:
        value = await r.get(key)
    finally:
        await r.aclose()
    return {"key": key, "value": value}


@router.put("/{key}")
async def redis_set(
    key: str,
    body: RedisSetBody,
    _: None = Depends(verify_service_token),
) -> dict:
    """Set a Redis key with optional TTL (seconds)."""
    r = _get_redis()
    try:
        if body.ttl:
            await r.setex(key, body.ttl, body.value)
        else:
            await r.set(key, body.value)
    finally:
        await r.aclose()
    return {"ok": True}


@router.delete("/{key}")
async def redis_delete(
    key: str,
    _: None = Depends(verify_service_token),
) -> dict:
    """Delete a Redis key."""
    r = _get_redis()
    try:
        await r.delete(key)
    finally:
        await r.aclose()
    return {"ok": True}
