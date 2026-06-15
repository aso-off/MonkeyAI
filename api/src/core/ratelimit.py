import asyncio

from fastapi import HTTPException, status

from core.logger import logger
from core.redis import get_redis


async def enforce_rate_limit(scope: str, identity: int | str, limit: int, window_seconds: int) -> None:
    """Fixed-window лимитер на Redis. 429 при превышении. Сбой Redis не блокирует запрос."""
    if limit <= 0:
        return
    key = f"ratelimit:{scope}:{identity}"
    try:
        r = get_redis()
        count = await asyncio.wait_for(r.incr(key), timeout=2.0)
        if count == 1:
            await asyncio.wait_for(r.expire(key, window_seconds), timeout=2.0)
    except Exception:
        logger.warning("Rate limit check skipped (Redis error) for %s", key)
        return
    if count > limit:
        ttl = await _safe_ttl(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry in {ttl}s.",
            headers={"Retry-After": str(ttl)},
        )


async def _safe_ttl(key: str) -> int:
    try:
        ttl = await asyncio.wait_for(get_redis().ttl(key), timeout=2.0)
        return ttl if ttl and ttl > 0 else 60
    except Exception:
        return 60