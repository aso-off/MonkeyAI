import asyncio

from fastapi import HTTPException, status

from core.config import settings
from core.logger import logger
from core.redis import get_redis


def limit_for(kind: str, is_premium: bool) -> int:
    """Лимит на окно по типу счётчика и тарифу. premium = Telegram Premium."""
    if kind == "image_gen":
        return settings.image_limit_premium if is_premium else settings.image_limit_default
    return settings.msg_limit_premium if is_premium else settings.msg_limit_default


def _key(kind: str, identity: int | str) -> str:
    return f"ratelimit:{kind}:{identity}"


# Атомарно: INCR + чинит TTL (на каждом вызове, не только первом) + откат при превышении.
# Возврат [limited(0|1), ttl]. Один RTT, гонки исключены (Redis выполняет скрипт целиком).
_CONSUME_LUA = """
local c = redis.call('INCR', KEYS[1])
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
  ttl = tonumber(ARGV[2])
end
if c > tonumber(ARGV[1]) then
  redis.call('DECR', KEYS[1])
  return {1, ttl}
end
return {0, ttl}
"""


async def _safe_ttl(key: str) -> int:
    try:
        ttl = await asyncio.wait_for(get_redis().ttl(key), timeout=2.0)
        return ttl if ttl and ttl > 0 else settings.limit_window_seconds
    except Exception:
        return settings.limit_window_seconds


async def consume_rate_limit(
    kind: str, user_id: int, is_premium: bool = False, is_admin: bool = False
) -> int | None:
    """Fixed-window от первого сообщения, атомарно (Lua). Списывает попытку.

    Возвращает None если разрешено, иначе retry_after (сек) до сброса.
    Админы без лимита. Сбой Redis - fail-open (None).
    """
    if is_admin:
        return None
    limit = limit_for(kind, is_premium)
    if limit <= 0:
        return None
    key = _key(kind, user_id)
    try:
        res = await asyncio.wait_for(
            get_redis().eval(_CONSUME_LUA, 1, key, limit, settings.limit_window_seconds),
            timeout=2.0,
        )
    except Exception:
        logger.warning("Rate limit check skipped (Redis error) for %s", key)
        return None
    limited, ttl = int(res[0]), int(res[1])
    if limited:
        return ttl if ttl > 0 else settings.limit_window_seconds
    return None


async def peek_rate_limit(
    kind: str, user_id: int, is_premium: bool = False, is_admin: bool = False
) -> int | None:
    """Проверка без списания (для голоса до Whisper). retry_after если уже исчерпан."""
    if is_admin:
        return None
    limit = limit_for(kind, is_premium)
    if limit <= 0:
        return None
    key = _key(kind, user_id)
    try:
        val = await asyncio.wait_for(get_redis().get(key), timeout=2.0)
    except Exception:
        return None
    used = int(val) if val else 0
    if used >= limit:
        return await _safe_ttl(key)
    return None


async def enforce_rate_limit(
    kind: str, user_id: int, is_premium: bool = False, is_admin: bool = False, *, consume: bool = True
) -> None:
    """429 при превышении; detail - структурный (kind/limit/retry_after) для локализации."""
    check = consume_rate_limit if consume else peek_rate_limit
    retry_after = await check(kind, user_id, is_premium, is_admin)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit",
                "kind": kind,
                "limit": limit_for(kind, is_premium),
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


async def read_usage(
    kind: str, user_id: int, is_premium: bool = False, is_admin: bool = False
) -> dict:
    """Текущая загрузка для индикатора: used/limit/percent(0-100)/reset_in(сек)."""
    if is_admin:
        return {"used": 0, "limit": 0, "percent": 0, "reset_in": 0}  # без лимита
    limit = limit_for(kind, is_premium)
    key = _key(kind, user_id)
    used = 0
    reset_in = 0
    try:
        val = await asyncio.wait_for(get_redis().get(key), timeout=2.0)
        if val:
            used = int(val)
            reset_in = await _safe_ttl(key)
    except Exception:
        pass
    used = min(used, limit)
    percent = min(100, round(used / limit * 100)) if limit > 0 else 0
    return {
        "used": used,
        "limit": limit,
        "percent": percent,
        "reset_in": reset_in if used else 0,
    }
