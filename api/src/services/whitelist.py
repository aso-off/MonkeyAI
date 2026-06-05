"""Общий с ботом Redis-сет разрешённых id (db 0). Гейт мини-аппа и бота читают его до БД."""

from core.redis import get_redis

ALLOWED_KEY = "auth:allowed"


async def rebuild(ids: set[int]) -> None:
    r = get_redis()
    await r.delete(ALLOWED_KEY)
    if ids:
        await r.sadd(ALLOWED_KEY, *ids)


async def add(user_id: int) -> None:
    await get_redis().sadd(ALLOWED_KEY, user_id)


async def remove(user_id: int) -> None:
    await get_redis().srem(ALLOWED_KEY, user_id)


async def is_allowed(user_id: int) -> bool | None:
    """True/False из сета; None — если Redis недоступен или сет не построен."""
    try:
        r = get_redis()
        if await r.sismember(ALLOWED_KEY, user_id):
            return True
        if await r.exists(ALLOWED_KEY):
            return False
        return None
    except Exception:
        return None
